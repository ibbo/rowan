# ChatSCD Changelog and Status Update Workflow

This repo uses a lightweight release-note process. The goal is to keep one human-readable changelog and make status updates predictable when releases affect users.

## Files

- `CHANGELOG.md`: ongoing release notes
- `docs/release_checklist.md`: deploy and rollback checklist
- `docs/emergency_runbook.md`: incident and rollback communications

## Changelog Rules

1. Add every user-visible, operational, or rollback-relevant change to `CHANGELOG.md` under `Unreleased`.
2. Keep entries short and operator-focused.
3. Prefer these buckets:
   - `Added`
   - `Changed`
   - `Fixed`
   - `Docs`
   - `Ops`
4. When a release is confirmed healthy, rename `Unreleased` into a dated release heading and start a new empty `Unreleased` section.
5. Include the deployed commit hash in the dated section if it is known at release time.

## When To Publish a Status Update

Publish a short status update when any of these are true:
- the release changes access policy, limits, sign-in requirements, or pricing posture
- there is visible downtime or a rollback
- a release changes trust, privacy, terms, or support surfaces

Skip the public status update when the release is internal-only and does not change user-facing behavior.

## Status Update Flow

### Routine Release

1. Before deploy, draft one sentence describing the user-visible change.
2. After deploy passes smoke checks, post:
   - what changed
   - whether any user action is needed
   - when the change took effect

### Incident or Rollback

1. Use the templates in [docs/emergency_runbook.md](emergency_runbook.md).
2. Post an initial update quickly.
3. Post a resolved update after rollback or mitigation is complete.

## Example Release Note Format

```markdown
## Unreleased

### Docs
- Added an incident runbook with kill switches, rollback steps, and comms templates.

### Ops
- Added a repeatable release checklist for deploy validation and rollback readiness.
```
