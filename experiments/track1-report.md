# Track 1 Report

## What I changed

- Added [`concept_resolver.py`](/Users/tamhas/Projects/rowan-accuracy-track1/concept_resolver.py), a lightweight canonical concept resolver that:
  - loads canonical formations from `formation`
  - loads canonical steps from `step`
  - normalizes query text and concept names
  - resolves exact aliases such as `2 couple allemande` -> `Allemande for 2 couples`
  - resolves step aliases such as `skip change` -> `Skip-Change`
  - flags family-level ambiguity such as `allemande` when multiple canonicals fit
- Updated [`scd_agent.py`](/Users/tamhas/Projects/rowan-accuracy-track1/scd_agent.py) to insert a deterministic `concept_grounder` stage before the planner:
  - exact non-technical matches add structured grounding to the planner prompt
  - ambiguous technical matches return a clarification request before the planner answers
  - exact technical matches return a grounded refusal when the RSCDS manual KB is unavailable, instead of improvising
- Added focused tests in [`test_concept_resolver.py`](/Users/tamhas/Projects/rowan-accuracy-track1/test_concept_resolver.py).

## What worked

- Target-style query `Where are the first couple in bar 2 of the 2 couple allemande?` now resolves to the exact canonical formation `Allemande for 2 couples` with token `ALLMND;2C;`.
- Generic technical query `How do I teach allemande?` now resolves as ambiguous and produces a clarification path instead of free-form guessing.
- Non-technical search query `Find dances with a reel of 3` resolves to the exact canonical formation `Reel of three` with token `REEL;R3;` and is allowed through to the planner with structured grounding.
- Step aliasing works for `How do I teach skip change?` -> `Skip-Change`.

## What did not work / limitations

- The current resolver is intentionally conservative. It uses exact normalization, alias rules, and simple constraint patterns; it does not do semantic paraphrase matching.
- I did not add new authoritative content for formation mechanics. When `data/manual/index.json` is missing, the agent now refuses detailed technique/position answers instead of improvising.
- I could syntax-check [`scd_agent.py`](/Users/tamhas/Projects/rowan-accuracy-track1/scd_agent.py), but I could not run the full LangGraph agent in this sandbox:
  - system `python3` does not have the project runtime deps like `langchain_core`
  - `uv run` panicked in this environment, so I validated the resolver and grounding logic directly instead

## Commands / tests run and results

- `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest test_concept_resolver.py`
  - Result: `Ran 5 tests ... OK`
- `PYTHONPYCACHEPREFIX=/tmp/rowan-pycache python3 -m py_compile concept_resolver.py scd_agent.py test_concept_resolver.py`
  - Result: success
- `PYTHONDONTWRITEBYTECODE=1 python3 - <<'PY' ...`
  - Result: sanity-checked the resolver on:
    - `Where are the first couple in bar 2 of the 2 couple allemande?`
    - `How do I teach allemande?`
    - `Find dances with a reel of 3`
    - `How do I teach skip change?`
  - Observed behavior matched the intended exact-match / ambiguity / grounded-refusal flow
