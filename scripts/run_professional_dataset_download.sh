#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

mkdir -p logs

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] professional dataset download start"
python3 scripts/run_professional_dataset_pipeline.py \
  --download-missing \
  --workers "${WORKERS:-1}" \
  --timeout-seconds "${TIMEOUT_SECONDS:-120}" \
  --max-retries "${MAX_RETRIES:-10}"
status=$?
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] professional dataset download exit status=${status}"
exit "$status"
