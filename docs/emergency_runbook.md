# ChatSCD Emergency Runbook

Use this document when ChatSCD needs immediate traffic control, abuse mitigation, or a fast rollback path during production incidents.

## Incident Triage

### First 10 Minutes

1. Confirm scope in `/admin` and `/admin/api/observability`:
   - request volume
   - error or blocked reasons
   - latency changes
   - donation click spikes if relevant to campaign traffic
2. Check `/health` for app readiness.
3. Identify blast radius:
   - anonymous-only
   - signed-in-only
   - all model-backed traffic
4. Decide whether the fastest safe response is:
   - rate reduction
   - anonymous shutdown
   - full model traffic stop
   - deployment rollback
5. Start an incident note with:
   - detection time
   - suspected cause
   - actions taken
   - next update time

### Severity Guide

- `SEV-1`: Site unavailable, runaway costs, or active abuse overwhelming the service. Apply kill switches immediately and prepare rollback.
- `SEV-2`: Elevated error rate, provider instability, or repeated anonymous abuse. Reduce traffic, monitor closely, and roll back if behavior persists.
- `SEV-3`: Minor degradation or isolated user reports. Investigate before changing traffic policy.

## Kill Switches and Env Toggles

Apply env var changes, restart the app, and verify the result after each change.

### 1. Disable all anonymous chat

```env
ANON_CHAT_ENABLED=false
```

Use when:
- anonymous abuse is severe
- provider cost or rate pressure requires an immediate traffic drop

Effect:
- all anonymous chat requests are blocked
- signed-in users can still use the app

Verify:
- `GET /api/anonymous-status` returns `"enabled": false`
- anonymous users see a sign-in-required state

### 2. Force sign-in after the free quota is exhausted

```env
ANON_REQUIRE_SIGNIN_AFTER_LIMIT=true
```

Use when:
- abuse is moderate and you want to preserve a small free tier
- you need a softer response than a full anonymous shutdown

Effect:
- anonymous users must authenticate after hitting the daily cap

### 3. Reduce or zero out the daily anonymous quota

```env
ANON_DAILY_MESSAGE_LIMIT=0
```

Use when:
- you need to stop new anonymous usage without changing the overall auth policy
- costs are rising faster than expected

Effect:
- no free anonymous messages are available after restart

### 4. Tighten burst protection

```env
ANON_BURST_WINDOW_SECONDS=60
ANON_BURST_MAX_REQUESTS=3
```

Use when:
- you see short-window request spikes
- upstream rate limits are firing
- you need to slow attackers without cutting off all anonymous traffic

Effect:
- reduces short-window request spikes from anonymous traffic

### 5. Keep production auth strict

```env
DEV_AUTH=false
```

Use when:
- validating production environment config
- investigating suspicious sign-in behavior

Effect:
- ensures the development login shortcut is disabled in production

### 6. Stop outbound model traffic entirely

Operational action:
- remove or rotate provider API keys such as `OPENAI_API_KEY`
- restart the app

Use when:
- provider misuse is suspected
- costs are running away
- the safest option is a full stop while investigation happens

Effect:
- model-backed chat requests stop succeeding until valid keys are restored

### Current High-Impact Toggles

```env
ANON_CHAT_ENABLED=true
ANON_DAILY_MESSAGE_LIMIT=5
ANON_REQUIRE_SIGNIN_AFTER_LIMIT=true
ANON_BURST_WINDOW_SECONDS=60
ANON_BURST_MAX_REQUESTS=8
DEV_AUTH=false
ADMIN_PASSWORD=changeme
```

Notes:
- `ADMIN_PASSWORD` is not a traffic kill switch, but it must be set and rotated if admin access is in doubt.
- `SUPPORT_EMAIL`, `SUPPORT_URL`, and `DONATION_URL` are public-facing only and do not change traffic safety behavior.

## Incident Playbooks

### Abuse Spike From Anonymous Traffic

1. Set `ANON_CHAT_ENABLED=false` if the spike is severe.
2. If partial service continuity is acceptable, keep anonymous chat on and tighten:
   - `ANON_DAILY_MESSAGE_LIMIT`
   - `ANON_BURST_MAX_REQUESTS`
   - `ANON_REQUIRE_SIGNIN_AFTER_LIMIT=true`
3. Restart the app.
4. Verify `/api/anonymous-status` and `/admin/api/observability`.
5. Post an incident status update if user-facing behavior changed.

### Error Burst or Provider Degradation

1. Review `/admin` error reasons and latency.
2. Reduce anonymous traffic with the kill switches above if the provider is degraded.
3. Stop outbound model traffic by rotating or removing provider API keys if errors are severe or costly.
4. Roll back to the previous known-good deployment if the issue is application-side.

### Cost Surge

1. Disable anonymous chat or set `ANON_DAILY_MESSAGE_LIMIT=0`.
2. Tighten burst limits.
3. Confirm whether a model selection or cost-estimation change caused the spike.
4. Re-enable traffic gradually once costs stabilize.

## Rollback Procedure

Use this when the application deployment is the likely cause and env toggles are not enough.

1. Identify the last known-good commit or release reference.
2. Record the current bad release commit and the rollback target in the incident note.
3. Re-deploy the previous known-good revision using the normal deploy path for this environment.
4. Restart the app or process manager.
5. Validate:
   - `/health`
   - `/api/anonymous-status`
   - `/admin`
   - one signed-in chat flow
   - one anonymous allowed or blocked flow, depending on intended policy
6. Leave emergency traffic restrictions in place if the root cause is still unknown.
7. Post a rollback status update and note the exact rollback time.

## Recovery Checklist

1. Restore env vars to the desired steady-state values only after the incident is contained.
2. Restart the app.
3. Re-run the validation checks:
   - `/health`
   - `/api/anonymous-status`
   - `/admin`
   - signed-in chat flow
   - anonymous blocked or allowed flow, depending on rollout mode
4. Capture:
   - incident timeline
   - env changes applied
   - deploy or rollback commit
   - follow-up actions

## Communication Template

### Internal Update

```text
Incident: <short title>
Severity: <SEV-1/2/3>
Started: <UTC timestamp>
Current impact: <who is affected and how>
Actions taken: <kill switch / rollback / provider action>
Next step: <what happens next>
Next update: <UTC timestamp>
```

### User-Facing Status Update

```text
We are investigating elevated issues affecting ChatSCD. Impact: <brief impact>.
Mitigation in progress: <what changed, for example anonymous access temporarily disabled>.
Next update by: <UTC timestamp>.
```

### Resolved Update

```text
ChatSCD service has been stabilized. Resolution: <rollback / config change / provider recovery>.
Customer impact window: <start-end UTC>.
Follow-up: we are reviewing the incident and any required permanent safeguards.
```
