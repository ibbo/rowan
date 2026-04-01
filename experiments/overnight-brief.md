# ChatSCD accuracy overnight brief

## Main branch / worktree
- Branch: `exp/chatscd-accuracy-2026-03-31`
- Worktree: `/Users/tamhas/Projects/rowan-accuracy-lab`

## Goal
Improve ChatSCD technical accuracy using ideas from the ChatGPT Pro share page, especially:
- canonical concept resolution before free-form answering
- lookup-first handling for deterministic technical questions
- validator/guardrail layer to block sibling-concept substitutions
- harsh confusion-set evals

## Advice summary
The most useful ideas from the external advice were:
1. Treat many SCD technical questions as state/lookups, not prose QA.
2. Resolve canonical entities first (figure/step/hold/etc.), not just semantically related text.
3. Use explicit constraints from the question (entity type, couples count, bar number, subject).
4. Add rule-based validators for impossible or sibling-substitution answers.
5. Build a contrastive eval set covering errors dancers would never make.

## Baseline observations
- The current agent routes many questions through free-form LLM + tools.
- `search_manual` depends on `data/manual/index.json`, which is currently missing in the Rowan repo/worktrees.
- When manual grounding is unavailable, the agent can still produce plausible but unsafe technical answers.
- Reproduced example from baseline:
  - Query: `Where are the first couple in bar 2 of the 2 couple allemande?`
  - Current behavior: admits manual is unavailable but still improvises a likely-wrong positioning answer.
- Existing DB data is useful for exact concept matching:
  - formations include `Allemande for 2 couples`, `Allemande Turn (to R or L)`, `Allemande for 3 couples`, etc.
  - steps include `Skip-Change`, `Pas-de-Basque`, etc.

## Parallel experiment tracks
- Track 1 worktree: `/Users/tamhas/Projects/rowan-accuracy-track1`
  - Goal: canonical concept resolver + structured grounding/disambiguation
  - Report target: `experiments/track1-report.md`
- Track 2 worktree: `/Users/tamhas/Projects/rowan-accuracy-track2`
  - Goal: validator / no-improvise safety layer for technical answers
  - Report target: `experiments/track2-report.md`
- Track 3 worktree: `/Users/tamhas/Projects/rowan-accuracy-track3`
  - Goal: contrastive eval harness + small high-signal dataset
  - Report target: `experiments/track3-report.md`

## Background Codex sessions
- Track 1 Codex exec session: `keen-comet`
- Track 2 Codex exec session: `cool-sage`
- Track 3 Codex exec session: `faint-otter`

## Morning deliverable
Create/update:
- `/Users/tamhas/Projects/rowan-accuracy-lab/experiments/morning-report.md`

The morning report should include:
- baseline failure summary
- what each experiment changed
- what worked
- what failed / stayed blocked
- which changes are worth cherry-picking or reimplementing onto `exp/chatscd-accuracy-2026-03-31`
- next recommended steps
