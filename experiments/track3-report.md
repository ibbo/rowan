# Track 3 Report

## What I changed

- Added a lightweight eval dataset at `experiments/track3_eval_cases.json`.
- Added a stdlib-only runner at `experiments/track3_eval.py`.
- Added regression tests for the scorer and dataset integrity in `test_track3_eval.py`.
- Ran and saved a practical baseline:
  - `experiments/track3-baseline-predictions.json`
  - `experiments/track3-baseline-report.json`

The dataset is deliberately small and contrastive. It targets:

- `2-couple allemande` vs `allemande turn`
- `skip change` vs `pas de basque`
- `travelling step` vs `setting step`
- exact bar-state questions that should be answered from crib evidence, not vibes
- one explicit abstention case for missing manual evidence

The scorer checks:

- required signals that should appear in an answer
- forbidden substitutions that should not appear
- a case-scoped confusion label, so the confusion matrix is about the relevant contrast for that prompt instead of arbitrary overlapping words

## What worked

- The harness runs with `python3` only. It does not depend on the missing project packages.
- The dataset is high-signal and harsh by design: most prompts name a specific dance, bar range, or formation variant.
- The confusion matrix is usable for regression tracking because label inference is constrained per case.
- The practical local baseline succeeded on all 11 cases:
  - overall: `11/11` passed
  - formation variants: `2/2`
  - step confusions: `5/5`
  - bar-state: `3/3`
  - evidence boundary: `1/1`

## What did not work / limitations

- I could not run a real live-agent baseline in this environment.
- `data/manual/index.json` is missing, so RSCDS manual lookup is not available locally.
- The installed `python3` does not have the project packages such as `aiosqlite` and `langchain_core`.
- `uv run` was not a viable fallback here. It first hit a sandboxed cache-path issue, and after redirecting cache it panicked in this environment.
- Because of those constraints, the runnable baseline is a deterministic SQLite/reference baseline plus abstention for missing-manual cases, not the current LLM-driven agent.
- The `data/` path in this worktree is a symlink to shared repo data outside the worktree. I used it read-only for baseline lookup and did not modify it.

## Commands run and results

```bash
python3 -m unittest -v test_track3_eval.py
```

Result:

- `6` tests passed

```bash
python3 experiments/track3_eval.py --baseline sqlite \
  --write-predictions experiments/track3-baseline-predictions.json \
  --output experiments/track3-baseline-report.json
```

Result:

- `11/11` passed
- confusion matrix rows:
  - `allemande_2c -> allemande_2c`
  - `allemande_turn -> allemande_turn`
  - `skip_change -> skip_change`
  - `pas_de_basque -> pas_de_basque`
  - `travelling_step -> travelling_step`
  - `setting_step -> setting_step` twice
  - `left_shoulder_pass -> left_shoulder_pass`
  - `cast_two_places -> cast_two_places`
  - `cross_left_hand -> cross_left_hand`
  - `insufficient_evidence -> insufficient_evidence`

## Suggested next use

When a model baseline is available, generate a predictions JSON keyed by case id and run:

```bash
python3 experiments/track3_eval.py --predictions path/to/predictions.json
```

That should make it easy to compare future model behavior against the same contrastive set.
