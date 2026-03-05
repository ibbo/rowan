# ChatSCD Release Checklist

Use this checklist for routine releases of the web app. It is intentionally lightweight and assumes the release target already has its deploy mechanism configured.

## Before Deploy

1. Confirm the branch and target commit are the ones intended for release.
2. Review `git diff` and make sure only intended changes are included.
3. Update `CHANGELOG.md` under `Unreleased` with user-facing changes, operational changes, and any notable rollback risk.
4. Review [docs/changelog_workflow.md](changelog_workflow.md) if the release needs a public status update.
5. Run the standard validation commands locally:

```bash
python3 -m py_compile web_app.py
uv run python test_chat_sessions.py
```

6. Confirm required env vars are present in the target environment:
   - provider API key
   - `ADMIN_PASSWORD`
   - auth secrets if OAuth is enabled
   - support and donation URLs if those links are expected to render
7. Verify that `DEV_AUTH=false` in production.
8. Know the rollback target before deploying.

## Deploy

1. Deploy the intended commit to the target environment.
2. Restart the app service or process manager.
3. Confirm startup succeeds and no immediate crash loop appears.
4. Run smoke checks:
   - `GET /health`
   - `GET /api/anonymous-status`
   - load `/`
   - load `/privacy`
   - load `/terms`
   - confirm `/admin` login still works
5. Run one signed-in chat request if auth is enabled.
6. Run one anonymous chat request to confirm gating and quota behavior.

## After Deploy

1. Watch `/admin` and `/admin/api/observability` for:
   - error rate
   - blocked reasons
   - latency
   - donation click anomalies if the release changed CTAs
2. Move the `Unreleased` changelog entries into a dated release section once the deploy is confirmed healthy.
3. Post the release status update if the change is externally visible.
4. Record the deployed commit hash and deploy timestamp in the release note or operator log.

## Rollback

If smoke checks fail or production errors rise materially, follow the rollback section in [docs/emergency_runbook.md](emergency_runbook.md).

Minimum rollback steps:
1. Deploy the last known-good commit.
2. Restart the app.
3. Re-run the smoke checks above.
4. Post a status update if users may have seen errors or changed availability.
