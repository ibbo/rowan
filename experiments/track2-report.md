# Track 2 Report

## What I changed

- Added a rule-based technical-query guard in `scd_agent.py`.
- Classified high-risk technical/manual questions separately from normal dance lookup questions.
- Added lookup-first routing for grounded technical questions:
  - exact RSCDS manual section numbers route to a deterministic manual answer
  - exact manual phrase matches route to the same deterministic answer path
- Added safe refusal/clarification when a technical question is not grounded:
  - manual KB unavailable
  - no exact manual term match
  - ambiguous compare-style questions with multiple manual terms
- Added `rejection_reason`, `safety_message`, and `grounded_manual_term` to agent state so the UI can distinguish off-topic rejection from technical safety rejection.
- Updated `web_app.py` SSE status handling to show a technical-grounding warning instead of incorrectly saying the query is not about Scottish Country Dancing.
- Added focused tests in `test_technical_guardrails.py` for:
  - technical query detection
  - longest exact manual alias selection
  - refusal when manual grounding is unavailable
  - prompt checker routing for grounded technical queries
  - refusal for ambiguous compare queries
  - deterministic exact-section answer generation

## What worked

- High-risk technical questions now avoid the normal freeform planner path unless they can be grounded to an exact RSCDS manual term or section.
- Grounded technical questions now bypass tool-planning and return a deterministic answer built from the exact manual section, which reduces concept substitution and sibling-concept drift.
- Normal dance search queries like “find dances with poussette” remain outside the technical guard path.
- The web UI can now surface a more accurate status message for technical safety rejections.

## What did not work / limitations

- The guard is intentionally narrow and rule-based. It focuses on high-risk technical/manual questions, not every possible SCD question shape.
- Compare-style technical questions are refused rather than answered; this is safer, but limited.
- The technical answer path currently returns the exact grounded manual section rather than a richer synthesized explanation.
- This worktree does not include a usable checked-in `data/manual` knowledge base, so in this environment many technical questions will correctly refuse rather than answer.
- `uv run pytest ...` was not usable in this sandbox:
  - first due an inaccessible default `uv` cache path
  - then due a `uv` runtime panic after redirecting cache to `/tmp`
- The system `python3` is 3.9, which is too old for this repo’s 3.12 syntax. I worked around that by using the local 3.12 interpreter already present under `~/.local/share/uv/python/...`.
- `pytest` was not installed in that 3.12 interpreter, so I made the new guardrail test file runnable as a plain Python script with local dependency stubs.

## Commands / tests run and results

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest test_technical_guardrails.py test_model_configuration.py`
  - failed: `uv` panicked in this sandbox after cache redirection
- `python3 -m pytest test_technical_guardrails.py test_model_configuration.py`
  - failed: system Python is 3.9, missing repo dependencies, and not compatible with the repo’s Python 3.12 typing syntax
- `/Users/tamhas/.local/share/uv/python/cpython-3.12.12-macos-aarch64-none/bin/python3.12 test_technical_guardrails.py`
  - passed: `All technical guardrail tests passed.`
- `/Users/tamhas/.local/share/uv/python/cpython-3.12.12-macos-aarch64-none/bin/python3.12 -m py_compile scd_agent.py web_app.py test_technical_guardrails.py`
  - passed
