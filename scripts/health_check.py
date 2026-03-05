#!/usr/bin/env python3
"""Simple periodic health check for ChatSCD."""

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib import error, request


DEFAULT_URL = os.getenv("HEALTH_CHECK_URL", "http://127.0.0.1:8000/health")
DEFAULT_DB_PATH = os.getenv("HEALTH_CHECK_DB_PATH", "data/chat_history.db")
DEFAULT_LOG_PATH = os.getenv("HEALTH_CHECK_LOG_PATH", "logs/uptime_checks.log")
DEFAULT_LABEL = os.getenv("HEALTH_CHECK_LABEL", "chatscd")
DEFAULT_TIMEOUT = float(os.getenv("HEALTH_CHECK_TIMEOUT_SECONDS", "10"))
DEFAULT_COOLDOWN_MINUTES = int(os.getenv("HEALTH_CHECK_ALERT_COOLDOWN_MINUTES", "30"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a ChatSCD health check and persist failures.")
    parser.add_argument("--url", default=DEFAULT_URL, help="Health endpoint URL")
    parser.add_argument("--db-path", default=DEFAULT_DB_PATH, help="SQLite DB path for alerts")
    parser.add_argument("--log-path", default=DEFAULT_LOG_PATH, help="Append-only log file path")
    parser.add_argument("--label", default=DEFAULT_LABEL, help="Label written into logs/alerts")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help="HTTP timeout in seconds")
    parser.add_argument(
        "--cooldown-minutes",
        type=int,
        default=DEFAULT_COOLDOWN_MINUTES,
        help="Suppress duplicate failure alerts inside this window",
    )
    return parser.parse_args()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def append_log(log_path: str, payload: dict) -> None:
    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def ensure_alerts_table(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS system_alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alert_type TEXT NOT NULL,
            severity TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'server',
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            details_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_system_alerts_created_at
        ON system_alerts(created_at)
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_system_alerts_type
        ON system_alerts(alert_type)
        """
    )
    conn.commit()


def persist_failure_alert(
    db_path: str,
    label: str,
    url: str,
    message: str,
    details: dict,
    cooldown_minutes: int,
) -> None:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        ensure_alerts_table(conn)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT 1
            FROM system_alerts
            WHERE alert_type = 'health_check_failed'
              AND source = 'uptime_check'
              AND created_at >= datetime('now', ?)
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (f"-{max(1, cooldown_minutes)} minutes",),
        )
        if cursor.fetchone():
            return

        cursor.execute(
            """
            INSERT INTO system_alerts (alert_type, severity, source, title, message, details_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "health_check_failed",
                "critical",
                "uptime_check",
                f"Health check failed ({label})",
                message,
                json.dumps({"label": label, "url": url, **details}),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def run_check(url: str, timeout: float) -> tuple[bool, dict]:
    req = request.Request(url, method="GET")
    try:
        with request.urlopen(req, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            data = json.loads(body) if body else {}
            status = data.get("status")
            ok = response.status == 200 and status == "healthy"
            return ok, {
                "status_code": response.status,
                "response": data,
                "message": "ok" if ok else f"unexpected health payload: status={status!r}",
            }
    except error.HTTPError as exc:
        return False, {
            "status_code": exc.code,
            "message": f"http error {exc.code}",
        }
    except error.URLError as exc:
        return False, {
            "status_code": None,
            "message": f"url error: {exc.reason}",
        }
    except json.JSONDecodeError:
        return False, {
            "status_code": 200,
            "message": "health endpoint did not return valid JSON",
        }


def main() -> int:
    args = parse_args()
    ok, details = run_check(args.url, args.timeout)
    log_payload = {
        "timestamp": utc_now(),
        "label": args.label,
        "url": args.url,
        "ok": ok,
        **details,
    }
    append_log(args.log_path, log_payload)

    if ok:
        print(f"health ok: {args.url}")
        return 0

    persist_failure_alert(
        db_path=args.db_path,
        label=args.label,
        url=args.url,
        message=f"Health check failed for {args.url}: {details.get('message', 'unknown error')}",
        details=details,
        cooldown_minutes=args.cooldown_minutes,
    )
    print(f"health failed: {details.get('message', 'unknown error')}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
