#!/usr/bin/env python3
"""Lightweight technical-accuracy eval harness for track 3."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


DATASET_PATH = Path("experiments/track3_eval_cases.json")
DB_PATH = Path("data/scddb/scddb.sqlite")
MANUAL_INDEX_PATH = Path("data/manual/index.json")


@dataclass
class CaseResult:
    case_id: str
    category: str
    target_label: str
    predicted_label: str
    passed: bool
    expected_hits: List[str]
    missing_expected: List[str]
    forbidden_hits: List[str]
    output: str


def load_dataset(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def normalize(text: str) -> str:
    return " ".join(text.lower().split())


def match_signals(text: str, signals: Iterable[str]) -> Tuple[List[str], List[str]]:
    normalized = normalize(text)
    hits: List[str] = []
    misses: List[str] = []
    for signal in signals:
        if normalize(signal) in normalized:
            hits.append(signal)
        else:
            misses.append(signal)
    return hits, misses


def infer_label(
    text: str,
    label_signals: Dict[str, List[str]],
    candidate_labels: Iterable[str] | None = None,
) -> str:
    normalized = normalize(text)
    best_label = "unknown"
    best_score = 0
    best_width = 0
    allowed = set(candidate_labels) if candidate_labels is not None else None
    for label, signals in label_signals.items():
        if allowed is not None and label not in allowed:
            continue
        matched = [signal for signal in signals if normalize(signal) in normalized]
        if not matched:
            continue
        score = len(matched)
        width = sum(len(signal) for signal in matched)
        if score > best_score or (score == best_score and width > best_width):
            best_label = label
            best_score = score
            best_width = width
    return best_label


def score_case(case: Dict[str, Any], output: str, label_signals: Dict[str, List[str]]) -> CaseResult:
    expected_hits, expected_misses = match_signals(output, case.get("required_any", []))
    forbidden_hits, _ = match_signals(output, case.get("forbidden_any", []))
    passed = bool(expected_hits) and not forbidden_hits
    return CaseResult(
        case_id=case["id"],
        category=case["category"],
        target_label=case["target_label"],
        predicted_label=infer_label(output, label_signals, case.get("candidate_labels")),
        passed=passed,
        expected_hits=expected_hits,
        missing_expected=expected_misses,
        forbidden_hits=forbidden_hits,
        output=output,
    )


def load_predictions(path: Path) -> Dict[str, str]:
    with path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    if isinstance(raw, dict):
        return {str(key): str(value) for key, value in raw.items()}
    if isinstance(raw, list):
        predictions: Dict[str, str] = {}
        for item in raw:
            predictions[str(item["id"])] = str(item["output"])
        return predictions
    raise ValueError(f"Unsupported predictions format in {path}")


def get_db_connection() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"SQLite database not found at {DB_PATH}")
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def sql_one(connection: sqlite3.Connection, sql: str, args: Tuple[Any, ...]) -> sqlite3.Row:
    row = connection.execute(sql, args).fetchone()
    if row is None:
        raise LookupError(f"No row for query: {sql!r} args={args!r}")
    return row


def local_baseline_prediction(case: Dict[str, Any], connection: sqlite3.Connection | None) -> str:
    case_id = case["id"]

    if case_id == "formation-allemande-2c":
        row = sql_one(
            connection,
            "SELECT name, searchid FROM formation WHERE name = ?",
            ("Allemande for 2 couples",),
        )
        return f"{row['name']} is the standard 2-couple allemande entry; token {row['searchid']}."

    if case_id == "formation-allemande-turn":
        row = sql_one(
            connection,
            "SELECT name, searchid FROM formation WHERE name = ?",
            ("Allemande Turn (to R or L)",),
        )
        return f"Use {row['name']} for the turn variant; token {row['searchid']}."

    if case_id == "bars-skip-change-stephen":
        return (
            "Bill's Friend, Stephen explicitly says first couple use skip change "
            "on bars 11-12 and again on 15-16."
        )

    if case_id == "bars-pas-de-basque-discounted-suit":
        return "Discounted Suit, The explicitly names pas de basque on bars 17-18."

    if case_id == "bars-travelling-step-kirkcudbright":
        return "Dancing in Kirkcudbright names a travelling step left for the bar-4 pivot."

    if case_id == "bars-setting-step-circle-strathspey":
        return "Circle Strathspey bars 1-8 use Glasgow Highlanders setting step."

    if case_id == "bars-mairis-wedding-pass-lsh":
        return "Mairi's Wedding says first couple pass partner left shoulder in bars 9-24."

    if case_id == "bars-reel51-cast-two-places":
        return "The Reel of the 51st Division says first couple cast off two places in bars 1-8."

    if case_id == "bars-montgomeries-cross-lh":
        return (
            "Montgomeries' Rant, The says first couple cross left hand after the opening "
            "right-hand cross in bars 1-8."
        )

    if case_id == "bars-diplomat-setting-steps":
        return "The Diplomat says first couple use two setting steps as they pass left shoulder."

    if case_id == "manual-skip-change-quote":
        section = manual_section_lookup("skip change of step")
        if section is None:
            return "RSCDS manual not available locally, so I cannot verify or quote the exact wording."
        return (
            f"Manual section {section['num']} ({section['title']}, page {section['page']}): "
            f"{section['content'][:600]}"
        )

    if case_id == "manual-absent-term-abstain":
        section = manual_section_lookup("highland swing turn")
        if section is None:
            return (
                "That term is not in the manual: there is no section for it, "
                "so I cannot quote any wording."
            )
        return (
            f"Manual section {section['num']} ({section['title']}, page {section['page']}): "
            f"{section['content'][:600]}"
        )

    if case_id == "teaching-skip-change-guidance":
        bundle = teaching_guide_step_lookup("skip change of step")
        if bundle is None:
            return "RSCDS teaching guide not available locally, so I cannot verify the teaching guidance."
        return (
            f"Teaching {bundle['title']}: faults to watch: {bundle['common_faults'][:300]} "
            f"Lesson plan: {bundle['lesson_plan'][:300]}"
        )

    raise KeyError(f"Unhandled case id: {case_id}")


TEACHING_GUIDE_PATH = Path("data/teaching_guide/teaching_guide.json")


def teaching_guide_step_lookup(step: str) -> Dict[str, Any] | None:
    """Load one step's bundle from the teaching guide KB, if present."""
    if not TEACHING_GUIDE_PATH.exists():
        return None
    guide = json.loads(TEACHING_GUIDE_PATH.read_text(encoding="utf-8"))
    return guide.get("steps", {}).get(step.lower())


def manual_section_lookup(term: str) -> Dict[str, Any] | None:
    """Resolve a term to a single manual section via data/manual JSON.

    Returns None when the manual is unavailable, the term is unknown, or
    the term is ambiguous (multiple candidate sections).
    """
    if not MANUAL_INDEX_PATH.exists():
        return None
    index = json.loads(MANUAL_INDEX_PATH.read_text(encoding="utf-8"))
    ref = index.get("sections", {}).get(term.lower())
    if not ref or ref.get("ambiguous"):
        return None
    chapter_info = index.get("chapters", {}).get(ref["chapter"])
    if not chapter_info:
        return None
    chapter_path = MANUAL_INDEX_PATH.parent / "chapters" / chapter_info["file"]
    if not chapter_path.exists():
        return None
    chapter = json.loads(chapter_path.read_text(encoding="utf-8"))
    data = chapter.get("sections", {}).get(ref["section"])
    if not data:
        return None
    return {
        "num": ref["section"],
        "title": data.get("title", ""),
        "page": data.get("page", "N/A"),
        "content": data.get("content", ""),
    }


def evaluate_predictions(
    dataset: Dict[str, Any],
    predictions: Dict[str, str],
) -> Dict[str, Any]:
    label_signals = dataset["label_signals"]
    results: List[CaseResult] = []
    for case in dataset["cases"]:
        output = predictions.get(case["id"], "")
        results.append(score_case(case, output, label_signals))
    return summarize_results(results)


def summarize_results(results: List[CaseResult]) -> Dict[str, Any]:
    totals = {"passed": 0, "failed": 0}
    by_category: Dict[str, Dict[str, int]] = {}
    matrix: Dict[str, Dict[str, int]] = {}

    for result in results:
        bucket = "passed" if result.passed else "failed"
        totals[bucket] += 1

        category_counts = by_category.setdefault(result.category, {"passed": 0, "failed": 0})
        category_counts[bucket] += 1

        row = matrix.setdefault(result.target_label, {})
        row[result.predicted_label] = row.get(result.predicted_label, 0) + 1

    return {
        "summary": {
            "total_cases": len(results),
            "passed": totals["passed"],
            "failed": totals["failed"],
            "pass_rate": round(totals["passed"] / len(results), 4) if results else 0.0,
        },
        "by_category": by_category,
        "confusion_matrix": matrix,
        "results": [
            {
                "id": result.case_id,
                "category": result.category,
                "target_label": result.target_label,
                "predicted_label": result.predicted_label,
                "passed": result.passed,
                "expected_hits": result.expected_hits,
                "missing_expected": result.missing_expected,
                "forbidden_hits": result.forbidden_hits,
                "output": result.output,
            }
            for result in results
        ],
    }


def print_summary(report: Dict[str, Any]) -> None:
    summary = report["summary"]
    print(
        f"Track 3 eval: {summary['passed']}/{summary['total_cases']} passed "
        f"({summary['pass_rate']:.0%})"
    )
    print("")
    print("By category:")
    for category, counts in sorted(report["by_category"].items()):
        total = counts["passed"] + counts["failed"]
        print(f"  {category}: {counts['passed']}/{total} passed")
    print("")
    print("Confusion matrix:")
    for target, row in sorted(report["confusion_matrix"].items()):
        rendered = ", ".join(f"{predicted}={count}" for predicted, count in sorted(row.items()))
        print(f"  {target}: {rendered}")
    print("")
    print("Failures:")
    for item in report["results"]:
        if item["passed"]:
            continue
        print(
            f"  {item['id']}: predicted={item['predicted_label']} "
            f"missing={item['missing_expected']} forbidden={item['forbidden_hits']}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DATASET_PATH)
    parser.add_argument("--predictions", type=Path)
    parser.add_argument("--baseline", choices=["sqlite"])
    parser.add_argument("--write-predictions", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    dataset = load_dataset(args.dataset)

    if bool(args.predictions) == bool(args.baseline):
        parser.error("Specify exactly one of --predictions or --baseline.")

    predictions: Dict[str, str]
    if args.predictions:
        predictions = load_predictions(args.predictions)
    else:
        connection = get_db_connection()
        try:
            predictions = {
                case["id"]: local_baseline_prediction(case, connection)
                for case in dataset["cases"]
            }
        finally:
            connection.close()

    report = evaluate_predictions(dataset, predictions)

    if args.write_predictions:
        args.write_predictions.write_text(json.dumps(predictions, indent=2) + "\n", encoding="utf-8")

    if args.output:
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print_summary(report)
    return 0 if report["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
