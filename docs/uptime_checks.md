# Uptime Checks and Alerting

This project includes a small cron-friendly health probe at `scripts/health_check.py`.

What it does:
- Sends a `GET` request to `/health`
- Appends a JSON log line to `logs/uptime_checks.log` (configurable)
- On failure or unhealthy response, writes a `health_check_failed` record into SQLite table `system_alerts`
- Suppresses duplicate failure alerts within a cooldown window

## Recommended Environment

Add these variables to `.env` if you want stable defaults for the script:

```bash
HEALTH_CHECK_URL=http://127.0.0.1:8000/health
HEALTH_CHECK_DB_PATH=data/chat_history.db
HEALTH_CHECK_LOG_PATH=logs/uptime_checks.log
HEALTH_CHECK_LABEL=chatscd-prod
HEALTH_CHECK_TIMEOUT_SECONDS=10
HEALTH_CHECK_ALERT_COOLDOWN_MINUTES=30
```

## Manual Run

```bash
uv run python scripts/health_check.py
```

Example with explicit paths:

```bash
uv run python scripts/health_check.py \
  --url http://127.0.0.1:8000/health \
  --db-path data/chat_history.db \
  --log-path logs/uptime_checks.log \
  --label chatscd-prod
```

Exit codes:
- `0`: health check passed
- `1`: health check failed and an alert was written (unless suppressed by cooldown)

## Cron Setup

Run the probe every 5 minutes:

```cron
*/5 * * * * cd /Users/tamhas/Projects/rowan-chat-access-gating && /usr/bin/env -S bash -lc 'uv run python scripts/health_check.py >> /tmp/chatscd-health-cron.log 2>&1'
```

Notes:
- Keep the working directory on the repo so relative DB/log paths resolve correctly.
- If the app runs on another host or port, set `HEALTH_CHECK_URL` or pass `--url`.
- Cron stdout/stderr can go to a separate file; the script also writes structured JSON lines to `HEALTH_CHECK_LOG_PATH`.

## Admin Visibility

Recent `health_check_failed` alerts appear in the admin dashboard under the observability alerts section alongside server-generated `high_error_rate` and `traffic_spike` alerts.
