#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="${REPO_DIR:-/opt/session-smc-trading-bot}"
cd "$REPO_DIR"

mkdir -p logs logs/candles

PYTHON_BIN="${PYTHON_BIN:-$REPO_DIR/.venv/bin/python}"
if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="${PYTHON_BIN_FALLBACK:-python3}"
fi

exec "$PYTHON_BIN" scripts/run_strategy_demo.py \
  --strategy SMCOrderBlockFVGSession \
  --mode demo \
  --interval 60
