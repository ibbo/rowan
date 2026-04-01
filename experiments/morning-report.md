# Rowan / ChatSCD accuracy morning report

_Status: updated during the 2026-04-01 04:30 Europe/London overnight sweep._

## Baseline
- Branch: `exp/chatscd-accuracy-2026-03-31`
- Worktree: `/Users/tamhas/Projects/rowan-accuracy-lab`
- Core reproduced issue: technical ChatSCD questions can still get plausible-but-unsafe answers when authoritative grounding is weak or unavailable.
- Shared blocker is still present: `search_manual` depends on `data/manual/index.json`, which is missing in these accuracy worktrees.

## Session re-check
- Re-checked the three overnight Codex tracks referenced as `keen-comet`, `cool-sage`, and `faint-otter`.
- No active/recent local exec sessions were still present by sweep time.
- The track worktrees all contained finished reports/artifacts, so the right move was consolidation rather than steering.

## Consolidated findings by track

### Track 1 — canonical concept resolver
**Worktree:** `/Users/tamhas/Projects/rowan-accuracy-track1`

**What changed**
- Added `concept_resolver.py` for exact canonical resolution of formations/steps from SQLite data.
- Added a `concept_grounder` stage in `scd_agent.py` before the planner.
- Exact technical concept matches now get canonical grounding; ambiguous family-level terms trigger clarification.
- Exact technical matches block with a grounded refusal when the manual KB is missing, instead of improvising.
- Added focused tests in `test_concept_resolver.py`.

**What worked**
- `2 couple allemande` resolves to `Allemande for 2 couples` (`ALLMND;2C;`).
- `skip change` resolves to `Skip-Change`.
- Generic technical family queries like `How do I teach allemande?` no longer guess and instead ask for clarification.
- Non-technical lookup-style queries like `Find dances with a reel of 3` still flow through, but with structured canonical grounding.

**Validation reviewed in track**
- `python3 -m unittest test_concept_resolver.py` -> passed (`5` tests)
- `py_compile` checks passed

**Port status**
- **Ported into main experiment worktree.**
- Landed files/changes:
  - `concept_resolver.py`
  - `test_concept_resolver.py`
  - `scd_agent.py` concept-grounding integration
  - `experiments/track1-report.md`

**Validation rerun in main worktree**
- `python3 -m unittest -v test_concept_resolver.py` -> passed (`5` tests)
- `python3 -m py_compile concept_resolver.py scd_agent.py test_concept_resolver.py` -> passed

**Assessment**
- This is now the strongest runtime idea: conservative, narrow, and directly aimed at sibling-concept substitutions.
- It is still limited by the missing manual KB, but that limitation is handled safely via refusal/clarification rather than hallucination.

### Track 2 — technical guardrail / no-improvise layer
**Worktree:** `/Users/tamhas/Projects/rowan-accuracy-track2`

**What changed**
- Added rule-based detection for high-risk technical/manual questions.
- Added lookup-first routing for exact manual terms/sections.
- Added deterministic grounded answers for exact manual matches.
- Added more accurate UI rejection/safety messaging in `web_app.py`.
- Added focused tests in `test_technical_guardrails.py`.

**What worked**
- Risky technique/manual questions stay off the normal free-form planner path unless exactly grounded.
- Exact manual section / phrase matches route to deterministic output rather than synthesis.
- Ungrounded technical questions refuse safely instead of being treated like off-topic rejections.

**Validation reviewed in track**
- `~/.local/share/uv/python/cpython-3.12.12-macos-aarch64-none/bin/python3.12 test_technical_guardrails.py` -> passed
- `py_compile` checks passed

**Port status**
- **Not ported yet.**
- Findings/report copied into main experiment worktree at `experiments/track2-report.md`.

**Why held back**
- More invasive than track 1 (`scd_agent.py` + `web_app.py`).
- Its value is capped until `data/manual/index.json` exists.
- Local validation depends on the non-default Python 3.12 interpreter path.

**Assessment**
- Strong safety posture, but best treated as the next layer after manual grounding is restored.

### Track 3 — contrastive eval harness
**Worktree:** `/Users/tamhas/Projects/rowan-accuracy-track3`

**What changed**
- Added `experiments/track3_eval.py` and `experiments/track3_eval_cases.json`.
- Added baseline artifacts:
  - `experiments/track3-baseline-predictions.json`
  - `experiments/track3-baseline-report.json`
- Added `test_track3_eval.py`.
- Built a small, harsh dataset covering formation variants, step confusions, bar-state questions, and an abstention case.

**What worked**
- Runner is stdlib-only and does not depend on the full LangGraph/runtime environment.
- Baseline evaluation is clean and practical.
- The dataset is suitable as a regression gate for future model/agent experiments.

**Validation reviewed in track**
- `python3 -m unittest -v test_track3_eval.py` -> passed (`6` tests)
- `python3 experiments/track3_eval.py --baseline sqlite ...` -> `11/11` passed

**Port status**
- **Already ported into main experiment worktree.**
- Landed files:
  - `experiments/track3_eval.py`
  - `experiments/track3_eval_cases.json`
  - `experiments/track3-baseline-predictions.json`
  - `experiments/track3-baseline-report.json`
  - `test_track3_eval.py`
  - `experiments/track3-report.md`

**Validation rerun in main worktree**
- `python3 -m unittest -v test_track3_eval.py` -> passed (`6` tests)
- `python3 experiments/track3_eval.py --baseline sqlite --write-predictions experiments/track3-baseline-predictions.json --output experiments/track3-baseline-report.json` -> `11/11` passed
- `python3 -m py_compile experiments/track3_eval.py test_track3_eval.py` -> passed

## What worked overall
- The clearest immediate win is now a **two-part result**:
  1. **Track 1** gave the best runtime idea and has been ported into the main experiment worktree as a conservative concept-grounding layer.
  2. **Track 3** gave the best evaluation win and is already usable as a shared regression harness.
- The combination is sensible: track 1 narrows/blocks unsafe technical answering, and track 3 gives a repeatable way to catch concept confusions.

## What did not work / current blockers
- `data/manual/index.json` is still missing, so neither runtime approach can produce authoritative detailed technical answers locally.
- Because the manual KB is missing, track 1 currently improves safety mainly by **refusing or clarifying**, not by unlocking new correct technical explanations.
- Track 2 remains partially blocked on the same missing manual KB and on heavier integration scope.
- `uv run` was still unreliable during this experiment cycle.
- Some repo validation paths still need the local Python 3.12 interpreter rather than system `python3`.
- No full live end-to-end agent benchmark against the new eval set has been run yet.

## Recommended next steps
1. Restore or generate `data/manual/index.json` first; that is still the main unlock for technical-accuracy work.
2. Once the manual KB exists, run end-to-end prompts through the **ported track 1 grounding path** against the contrastive eval cases.
3. If track 1 behaves well with real manual grounding, then port selected **track 2** guardrail pieces next, especially the deterministic exact-manual answer path.
4. Keep using `experiments/track3_eval.py` as the shared regression gate for every further ChatSCD accuracy iteration.
5. Add a small live-agent prediction export path next, so the same track 3 cases can score actual agent/model outputs instead of only the SQLite/reference baseline.
