#!/usr/bin/env python3
"""Side-by-side model comparison for the ChatSCD agents.

Runs the same prompts through the real SCDAgent / LessonPlannerAgent for
each model, auto-scores the track-3 accuracy cases, applies per-prompt
checks (RSCDS-only picks, expected tool usage, ...), and writes JSON,
markdown and HTML reports to experiments/compare-<timestamp>/.

Usage (from the repo root):
    uv run experiments/model_compare.py --models gpt-5.4-mini gpt-5.6-luna
    uv run experiments/model_compare.py --models ... --only track3
    uv run experiments/model_compare.py --models ... --limit 1   # smoke test

Only the answering model changes between runs: the prompt checker always
uses the provider's fast model, and the database / manual KB are shared.
"""

from __future__ import annotations

import argparse
import asyncio
import html
import json
import re
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(REPO_ROOT / ".env")

from langchain_core.messages import AIMessage  # noqa: E402

from lesson_planner import LessonPlannerAgent  # noqa: E402
from scd_agent import SCDAgent  # noqa: E402
from track3_eval import load_dataset, score_case  # noqa: E402

TRACK3_CASES = REPO_ROOT / "experiments" / "track3_eval_cases.json"
FREEFORM_PROMPTS = REPO_ROOT / "experiments" / "compare_prompts.json"
DB_PATH = REPO_ROOT / "data" / "scddb" / "scddb.sqlite"

DANCE_LINK = re.compile(r"strathspey\.org/dd/dance/(\d+)")


def message_text(content: Any) -> str:
    """AIMessage.content is a string on chat-completions but a list of
    blocks on the Responses API; return the plain text either way."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "".join(parts)
    return str(content or "")


# ---------------------------------------------------------------------------
# Running prompts through the agents
# ---------------------------------------------------------------------------

async def run_prompt(agent, prompt: str, run_id: str) -> Dict[str, Any]:
    """Run one prompt on a fresh conversation thread; capture everything."""
    config = {"configurable": {"thread_id": run_id}}
    started = time.perf_counter()
    error = None
    result = None
    try:
        result = await agent.ainvoke(prompt, config)
    except Exception as exc:  # keep going; the report shows the failure
        error = f"{type(exc).__name__}: {exc}"
    latency = time.perf_counter() - started

    answer = ""
    tool_calls: List[Dict[str, Any]] = []
    usage = {"input": 0, "output": 0, "reasoning": 0, "llm_calls": 0}

    if result:
        for msg in result["messages"]:
            if not isinstance(msg, AIMessage):
                continue
            usage["llm_calls"] += 1
            for call in msg.tool_calls or []:
                tool_calls.append({"name": call["name"], "args": call["args"]})
            meta = getattr(msg, "usage_metadata", None) or {}
            usage["input"] += meta.get("input_tokens", 0)
            usage["output"] += meta.get("output_tokens", 0)
            usage["reasoning"] += (meta.get("output_token_details") or {}).get("reasoning", 0)
        for msg in reversed(result["messages"]):
            if isinstance(msg, AIMessage) and not msg.tool_calls and message_text(msg.content).strip():
                answer = message_text(msg.content)
                break

    return {
        "answer": answer,
        "error": error,
        "latency_s": round(latency, 1),
        "tool_calls": tool_calls,
        "usage": usage,
    }


# ---------------------------------------------------------------------------
# Checks on freeform prompts
# ---------------------------------------------------------------------------

def rscds_flags(dance_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    """Map dance id -> {name, rscds} from the local SCDDB."""
    if not dance_ids:
        return {}
    conn = sqlite3.connect(DB_PATH)
    placeholders = ",".join("?" * len(dance_ids))
    rows = conn.execute(
        f"""
        SELECT d.id, d.name, COALESCE(MAX(p.rscds), 0) AS rscds
        FROM dance d
        LEFT JOIN dancespublicationsmap dpm ON dpm.dance_id = d.id
        LEFT JOIN publication p ON p.id = dpm.publication_id
        WHERE d.id IN ({placeholders})
        GROUP BY d.id
        """,
        [int(i) for i in dance_ids],
    ).fetchall()
    conn.close()
    return {str(r[0]): {"name": r[1], "rscds": bool(r[2])} for r in rows}


def apply_checks(spec: Dict[str, Any], run: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    checks = spec.get("checks", {})
    answer = run["answer"]
    lowered = " ".join(answer.lower().split())
    used_tools = {call["name"] for call in run["tool_calls"]}
    out: Dict[str, Dict[str, Any]] = {}

    linked = sorted(set(DANCE_LINK.findall(answer)))
    if checks.get("rscds_only"):
        flags = rscds_flags(linked)
        non_rscds = [f"{v['name']} ({k})" for k, v in flags.items() if not v["rscds"]]
        out["rscds_only"] = {
            "passed": bool(linked) and not non_rscds,
            "detail": f"{len(linked)} dances linked; non-RSCDS: {non_rscds or 'none'}",
        }
    if "min_dance_links" in checks:
        out["min_dance_links"] = {
            "passed": len(linked) >= checks["min_dance_links"],
            "detail": f"{len(linked)} linked (need {checks['min_dance_links']})",
        }
    if "required_tools" in checks:
        missing = sorted(set(checks["required_tools"]) - used_tools)
        out["required_tools"] = {
            "passed": not missing,
            "detail": f"missing: {missing or 'none'}; used: {sorted(used_tools)}",
        }
    if "expect_any" in checks:
        hits = [s for s in checks["expect_any"] if s.lower() in lowered]
        out["expect_any"] = {"passed": bool(hits), "detail": f"hits: {hits or 'none'}"}
    if "forbid_any" in checks:
        hits = [s for s in checks["forbid_any"] if s.lower() in lowered]
        out["forbid_any"] = {"passed": not hits, "detail": f"forbidden hits: {hits or 'none'}"}
    if run["error"]:
        out["no_error"] = {"passed": False, "detail": run["error"]}
    return out


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

async def run_model(model: str, items: List[Dict[str, Any]], label_signals: Dict[str, List[str]], stamp: str) -> List[Dict[str, Any]]:
    chat_agent = SCDAgent(provider="openai", model=model, temperature=0)
    planner_agent = LessonPlannerAgent(provider="openai", model=model, temperature=0)
    results = []
    for index, item in enumerate(items, 1):
        agent = planner_agent if item.get("mode") == "planner" else chat_agent
        print(f"[{model}] {index}/{len(items)} {item['id']} ...", file=sys.stderr, flush=True)
        run = await run_prompt(agent, item["prompt"], f"cmp-{stamp}-{model}-{item['id']}")
        entry = {"id": item["id"], "model": model, **run}
        if item["kind"] == "track3":
            scored = score_case(item["case"], run["answer"], label_signals)
            entry["score"] = {
                "passed": scored.passed,
                "predicted_label": scored.predicted_label,
                "target_label": scored.target_label,
                "missing_expected": scored.missing_expected,
                "forbidden_hits": scored.forbidden_hits,
            }
        else:
            checks = apply_checks(item, run)
            entry["checks"] = checks
            entry["score"] = {"passed": all(c["passed"] for c in checks.values()) if checks else None}
        status = "PASS" if entry["score"]["passed"] else ("n/a" if entry["score"]["passed"] is None else "FAIL")
        print(f"[{model}]   -> {status} in {run['latency_s']}s, {len(run['tool_calls'])} tool calls, "
              f"{run['usage']['input']}+{run['usage']['output']} tokens", file=sys.stderr, flush=True)
        results.append(entry)
    return results


def build_items(only: str | None, limit: int | None, repeat: int = 1) -> tuple[List[Dict[str, Any]], Dict[str, List[str]]]:
    dataset = load_dataset(TRACK3_CASES)
    items: List[Dict[str, Any]] = []
    if only in (None, "track3"):
        for case in dataset["cases"]:
            items.append({"id": case["id"], "kind": "track3", "mode": "chat",
                          "prompt": case["prompt"], "category": case["category"], "case": case})
    if only in (None, "prompts") and FREEFORM_PROMPTS.exists():
        for spec in json.loads(FREEFORM_PROMPTS.read_text(encoding="utf-8")):
            items.append({**spec, "kind": "freeform", "category": spec.get("category", "freeform")})
    if limit:
        track3 = [i for i in items if i["kind"] == "track3"][:limit]
        free = [i for i in items if i["kind"] == "freeform"][:limit]
        items = track3 + free
    if repeat > 1:
        # Same prompt several times: pass rates then reflect run-to-run
        # variance rather than a single lucky/unlucky draw
        items = [
            {**item, "id": f"{item['id']}#{rep}", "base_id": item["id"]}
            for rep in range(1, repeat + 1)
            for item in items
        ]
    return items, dataset["label_signals"]


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

def summarize(model: str, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    scored = [r for r in rows if r["score"]["passed"] is not None]
    t3 = [r for r in rows if "category" in r and r.get("kind") == "track3"]
    return {
        "model": model,
        "runs": len(rows),
        "errors": sum(1 for r in rows if r["error"]),
        "passed": sum(1 for r in scored if r["score"]["passed"]),
        "scored": len(scored),
        "avg_latency_s": round(sum(r["latency_s"] for r in rows) / len(rows), 1) if rows else 0,
        "avg_tool_calls": round(sum(len(r["tool_calls"]) for r in rows) / len(rows), 1) if rows else 0,
        "input_tokens": sum(r["usage"]["input"] for r in rows),
        "output_tokens": sum(r["usage"]["output"] for r in rows),
        "reasoning_tokens": sum(r["usage"]["reasoning"] for r in rows),
    }


def write_markdown(path: Path, models: List[str], items: List[Dict[str, Any]], by_model: Dict[str, List[Dict[str, Any]]], summaries: List[Dict[str, Any]]) -> None:
    lines = [f"# Model comparison — {datetime.now():%Y-%m-%d %H:%M}", ""]
    lines.append("| Model | Passed | Errors | Avg latency | Avg tool calls | Input tokens | Output tokens | of which reasoning |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for s in summaries:
        lines.append(f"| {s['model']} | {s['passed']}/{s['scored']} | {s['errors']} | {s['avg_latency_s']}s | "
                     f"{s['avg_tool_calls']} | {s['input_tokens']:,} | {s['output_tokens']:,} | {s['reasoning_tokens']:,} |")
    lines += ["", "## Per-prompt results", ""]
    header = "| Prompt | " + " | ".join(models) + " |"
    lines += [header, "|---|" + "---|" * len(models)]
    for idx, item in enumerate(items):
        cells = []
        for m in models:
            r = by_model[m][idx]
            p = r["score"]["passed"]
            mark = "✅" if p else ("—" if p is None else "❌")
            cells.append(f"{mark} {r['latency_s']}s / {len(r['tool_calls'])} tools")
        lines.append(f"| {item['id']} | " + " | ".join(cells) + " |")
    lines += ["", "## Answers side by side", ""]
    for idx, item in enumerate(items):
        lines += [f"### {item['id']}", "", f"**Prompt:** {item['prompt']}", ""]
        for m in models:
            r = by_model[m][idx]
            lines.append(f"#### {m} — {'PASS' if r['score']['passed'] else ('unscored' if r['score']['passed'] is None else 'FAIL')}"
                         f" ({r['latency_s']}s, {len(r['tool_calls'])} tool calls, {r['usage']['input']}+{r['usage']['output']} tokens)")
            if r.get("checks"):
                for name, c in r["checks"].items():
                    lines.append(f"- {'✅' if c['passed'] else '❌'} {name}: {c['detail']}")
            if r.get("score", {}).get("missing_expected") or r.get("score", {}).get("forbidden_hits"):
                lines.append(f"- missing: {r['score']['missing_expected']}; forbidden: {r['score']['forbidden_hits']}")
            lines.append(f"- tools: {', '.join(c['name'] for c in r['tool_calls']) or 'none'}")
            lines += ["", (r["answer"] or f"*(no answer: {r['error']})*").strip(), ""]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_html(path: Path, models: List[str], items: List[Dict[str, Any]], by_model: Dict[str, List[Dict[str, Any]]], summaries: List[Dict[str, Any]]) -> None:
    def esc(s: Any) -> str:
        return html.escape(str(s))

    parts = [f"""<!doctype html><html><head><meta charset="utf-8"><title>Model comparison</title>
<script src="https://cdn.jsdelivr.net/npm/marked@11.1.1/marked.min.js"></script>
<style>
body{{font-family:-apple-system,Segoe UI,Roboto,sans-serif;margin:24px;color:#22272b;background:#f5f4f0}}
table.sum{{border-collapse:collapse;margin-bottom:24px}} table.sum td,table.sum th{{border:1px solid #d6d3ca;padding:6px 10px;font-size:.9rem}}
.case{{background:#fff;border:1px solid #e5e3dc;border-radius:10px;padding:16px;margin-bottom:18px}}
.prompt{{font-weight:600;margin-bottom:10px}}
.cols{{display:grid;grid-template-columns:repeat({len(models)},1fr);gap:14px}}
.col{{border:1px solid #e5e3dc;border-radius:8px;padding:12px;min-width:0;overflow-wrap:anywhere}}
.col h4{{margin:0 0 6px;font-size:.95rem}} .pass{{color:#1f6e5a}} .fail{{color:#b3382f}}
.meta{{font-size:.78rem;color:#6d7378;margin-bottom:8px}} .answer{{font-size:.88rem;line-height:1.45}}
.answer table{{border-collapse:collapse}} .answer td,.answer th{{border:1px solid #ddd;padding:3px 6px;font-size:.8rem}}
</style></head><body><h1>Model comparison — {datetime.now():%Y-%m-%d %H:%M}</h1>
<table class="sum"><tr><th>Model</th><th>Passed</th><th>Errors</th><th>Avg latency</th><th>Avg tool calls</th><th>Input tokens</th><th>Output tokens</th><th>Reasoning tokens</th></tr>"""]
    for s in summaries:
        parts.append(f"<tr><td>{esc(s['model'])}</td><td>{s['passed']}/{s['scored']}</td><td>{s['errors']}</td><td>{s['avg_latency_s']}s</td>"
                     f"<td>{s['avg_tool_calls']}</td><td>{s['input_tokens']:,}</td><td>{s['output_tokens']:,}</td><td>{s['reasoning_tokens']:,}</td></tr>")
    parts.append("</table>")
    for idx, item in enumerate(items):
        parts.append(f'<div class="case"><div class="prompt">{esc(item["id"])} — {esc(item["prompt"])}</div><div class="cols">')
        for m in models:
            r = by_model[m][idx]
            p = r["score"]["passed"]
            status = '<span class="pass">PASS</span>' if p else ('unscored' if p is None else '<span class="fail">FAIL</span>')
            checks = "".join(f"<div>{'✅' if c['passed'] else '❌'} {esc(name)}: {esc(c['detail'])}</div>" for name, c in (r.get("checks") or {}).items())
            score_detail = ""
            if r["score"].get("missing_expected") or r["score"].get("forbidden_hits"):
                score_detail = f"<div>missing: {esc(r['score']['missing_expected'])}; forbidden: {esc(r['score']['forbidden_hits'])}</div>"
            tools = ", ".join(c["name"] for c in r["tool_calls"]) or "none"
            answer = r["answer"] or f"(no answer: {r['error']})"
            parts.append(f'<div class="col"><h4>{esc(m)} — {status}</h4><div class="meta">{r["latency_s"]}s · {len(r["tool_calls"])} tool calls · '
                         f'{r["usage"]["input"]}+{r["usage"]["output"]} tokens ({r["usage"]["reasoning"]} reasoning)<br>tools: {esc(tools)}{checks}{score_detail}</div>'
                         f'<div class="answer" data-md="{esc(answer)}"></div></div>')
        parts.append("</div></div>")
    parts.append("""<script>document.querySelectorAll('.answer').forEach(el=>{el.innerHTML=window.marked?marked.parse(el.dataset.md):'<pre>'+el.dataset.md+'</pre>';});</script></body></html>""")
    path.write_text("".join(parts), encoding="utf-8")


def rescore(run_dir: Path, only: str | None, limit: int | None, repeat: int = 1) -> int:
    """Re-apply scoring/checks to a saved run and regenerate its reports."""
    by_model: Dict[str, List[Dict[str, Any]]] = json.loads((run_dir / "results.json").read_text(encoding="utf-8"))
    items, label_signals = build_items(only, limit, repeat)
    by_id = {item["id"]: item for item in items}
    models = list(by_model)
    for model, rows in by_model.items():
        for row in rows:
            item = by_id.get(row["id"])
            if item is None:
                continue
            if item["kind"] == "track3":
                scored = score_case(item["case"], row["answer"], label_signals)
                row["score"] = {
                    "passed": scored.passed,
                    "predicted_label": scored.predicted_label,
                    "target_label": scored.target_label,
                    "missing_expected": scored.missing_expected,
                    "forbidden_hits": scored.forbidden_hits,
                }
            else:
                checks = apply_checks(item, row)
                row["checks"] = checks
                row["score"] = {"passed": all(c["passed"] for c in checks.values()) if checks else None}
    # Keep the item order of the saved run
    ordered_items = [by_id[r["id"]] for r in by_model[models[0]] if r["id"] in by_id]
    (run_dir / "results.json").write_text(json.dumps(by_model, indent=2), encoding="utf-8")
    summaries = [summarize(m, by_model[m]) for m in models]
    write_markdown(run_dir / "report.md", models, ordered_items, by_model, summaries)
    write_html(run_dir / "report.html", models, ordered_items, by_model, summaries)
    for s in summaries:
        print(f"{s['model']}: {s['passed']}/{s['scored']} passed, {s['errors']} errors, avg {s['avg_latency_s']}s, "
              f"{s['input_tokens']:,} in / {s['output_tokens']:,} out ({s['reasoning_tokens']:,} reasoning)", file=sys.stderr)
    print(f"\nRe-scored reports: {run_dir}/report.md and report.html", file=sys.stderr)
    return 0


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--models", nargs="+", help="model specs to run (required unless --rescore)")
    parser.add_argument("--only", choices=["track3", "prompts"])
    parser.add_argument("--limit", type=int, help="run only the first N of each kind (smoke test)")
    parser.add_argument("--repeat", type=int, default=1, help="run each prompt N times to expose run-to-run variance")
    parser.add_argument("--out", type=Path, help="output directory (default experiments/compare-<timestamp>)")
    parser.add_argument("--rescore", type=Path, metavar="DIR",
                        help="re-score an existing run's results.json with the current scorer (no LLM calls)")
    args = parser.parse_args()

    if args.rescore:
        return rescore(args.rescore, args.only, args.limit, args.repeat)
    if not args.models:
        parser.error("--models is required unless --rescore is given")

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = args.out or (REPO_ROOT / "experiments" / f"compare-{stamp}")
    out_dir.mkdir(parents=True, exist_ok=True)

    items, label_signals = build_items(args.only, args.limit, args.repeat)
    print(f"Running {len(items)} prompts × {len(args.models)} models -> {out_dir}", file=sys.stderr)

    by_model: Dict[str, List[Dict[str, Any]]] = {}
    for model in args.models:
        rows = await run_model(model, items, label_signals, stamp)
        for row, item in zip(rows, items):
            row["kind"] = item["kind"]
            row["category"] = item["category"]
        by_model[model] = rows
        (out_dir / "results.json").write_text(json.dumps(by_model, indent=2), encoding="utf-8")

    summaries = [summarize(m, by_model[m]) for m in args.models]
    write_markdown(out_dir / "report.md", args.models, items, by_model, summaries)
    write_html(out_dir / "report.html", args.models, items, by_model, summaries)

    print("", file=sys.stderr)
    for s in summaries:
        print(f"{s['model']}: {s['passed']}/{s['scored']} passed, {s['errors']} errors, avg {s['avg_latency_s']}s, "
              f"{s['input_tokens']:,} in / {s['output_tokens']:,} out ({s['reasoning_tokens']:,} reasoning)", file=sys.stderr)
    print(f"\nReports: {out_dir}/report.md and report.html", file=sys.stderr)

    # The aiosqlite pool's threads keep the interpreter alive otherwise
    from database import DatabasePool
    pool = await DatabasePool.get_instance()
    await pool.close_all()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
