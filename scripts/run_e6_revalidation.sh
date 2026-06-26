#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║  E6 Cost Revalidation Pipeline — ST-A2              ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

echo "[Step 0] Checking Phase 2 collection gate ..."
python3 scripts/check_phase2_completion.py
echo ""

echo "[Step 1] Running comprehensive spread analysis ..."
python3 research/analyze_spreads.py
echo ""

echo "[Step 2] Building cost model ..."
python3 scripts/build_cost_model.py
echo ""

echo "[Step 3] Exporting measured spread limits ..."
python3 scripts/export_spread_limits.py
echo ""

echo "[Step 4] Running ST-A2 backtest with measured Vantage costs ..."
python3 scripts/backtest_session_liquidity.py \
  --costs-json config/costs.json \
  --json-out reports/backtest/ST-A2_e6_backtest.json
echo ""

echo "[Step 5] Running validation gate ..."
python3 scripts/run_validation_gate.py \
  --strategy ST-A2 \
  --mode backtest \
  --backtest-json reports/backtest/ST-A2_e6_backtest.json \
  --latest-json reports/backtest/ST-A2_e6_backtest.json \
  --stage backtest \
  --outdir reports/validation
echo ""

echo "╔══════════════════════════════════════════════════════╗"
echo "║  E6 Pipeline Complete                                ║"
echo "╚══════════════════════════════════════════════════════╝"
