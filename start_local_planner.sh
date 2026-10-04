#!/bin/sh
# Local-only app preview, with separate chat/settings databases.
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
mkdir -p data/local-preview
export CHAT_DB_PATH="$PWD/data/local-preview/chat.db"
export SETTINGS_DB_PATH="$PWD/data/local-preview/settings.db"
exec .venv/bin/python -m uvicorn web_app:app --host 127.0.0.1 --port "${CHAT_SCD_LOCAL_PORT:-8015}"
