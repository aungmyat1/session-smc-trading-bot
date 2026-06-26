#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="${REPO_DIR:-/opt/session-smc-trading-bot}"
cd "$REPO_DIR"

mkdir -p logs
PYTHON_BIN="${PYTHON_BIN:-$REPO_DIR/.venv/bin/python}"
if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="${PYTHON_BIN_FALLBACK:-python3}"
fi
exec env \
  DEMO_LIVE="${DEMO_LIVE:-false}" \
  LIVE_TRADING="${LIVE_TRADING:-false}" \
  "$PYTHON_BIN" scripts/run_d2_e3_demo.py >> logs/d2e3_demo.log 2>&1
