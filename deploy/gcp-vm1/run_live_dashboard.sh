#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="${REPO_DIR:-/opt/session-smc-trading-bot}"
cd "$REPO_DIR"

mkdir -p logs
PYTHON_BIN="${PYTHON_BIN:-$REPO_DIR/.venv/bin/python}"
if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="${PYTHON_BIN_FALLBACK:-python3}"
fi

PORT="${LIVE_DASHBOARD_PORT:-8090}"

exec env \
  DASHBOARD_PORT="${DASHBOARD_PORT:-8080}" \
  LIVE_DASHBOARD_PORT="$PORT" \
  LIVE_TRADING="${LIVE_TRADING:-false}" \
  "$PYTHON_BIN" -m uvicorn dashboard.status_server:app \
    --host 0.0.0.0 --port "$PORT" --log-level warning
