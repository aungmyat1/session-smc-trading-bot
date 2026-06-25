#!/usr/bin/env bash
# ============================================================
# E6 Cost Revalidation Pipeline
# Session Liquidity Bot — ST-A2 with measured Vantage costs
#
# PREREQUISITES (all must be true before running):
#   1. check_phase2_completion.py exits 0  (≥5 London, ≥5 NY, ≥7,000 rows)
#   2. OPS-01 stability run complete       (through 2026-06-28)
#   3. research/spread_samples.csv has no unexplained gaps during killzones
#
# USAGE:
#   cd ~/session-smc-trading-bot
#   bash scripts/run_e6_revalidation.sh
#
# DO NOT RUN until check_phase2_completion.py exits 0.
# DO NOT MODIFY: strategy code, risk settings, LIVE_TRADING, or .env.
# This script only changes: config/costs.json (active_profile + vantage_measured values).
# ============================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║  E6 Cost Revalidation Pipeline — ST-A2              ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

# ── Step 0: Gate check ────────────────────────────────────────────────────────
echo "[Step 0] Checking Phase 2 collection gate ..."
if ! python3 scripts/check_phase2_completion.py; then
    echo ""
    echo "[BLOCKED] Phase 2 collection not yet complete."
    echo "          Run again after gate is met (≥5 London + ≥5 NY + ≥7,000 rows)."
    exit 1
fi
echo ""

# ── Step 1: Comprehensive spread analysis → SPREAD_RESEARCH_FINAL_REPORT.md ──
echo "[Step 1] Running comprehensive spread analysis ..."
python3 research/analyze_spreads.py
echo ""

# ── Step 2: Build cost model JSON ─────────────────────────────────────────────
echo "[Step 2] Building cost model (avg / median / P90 / P95 / P99) ..."
python3 scripts/build_cost_model.py
echo ""

# ── Step 3: Export spread limits + update costs.json ─────────────────────────
echo "[Step 3] Exporting spread limits and updating config/costs.json ..."
python3 scripts/export_spread_limits.py
echo ""

# ── Step 4: Re-run ST-A2 backtest with measured costs ────────────────────────
echo "[Step 4] Running ST-A2 backtest with measured Vantage costs ..."
echo "         (config/costs.json → active_profile: vantage_measured)"
python3 scripts/backtest_session_liquidity.py --costs-json config/costs.json
echo ""

# ── Step 5: Summary ───────────────────────────────────────────────────────────
echo "╔══════════════════════════════════════════════════════╗"
echo "║  E6 Pipeline Complete                                ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""
echo "Files updated:"
echo "  docs/SPREAD_RESEARCH_FINAL_REPORT.md    ← spread analysis report"
echo "  research/cost_model.json                ← P95/avg/median per symbol/session"
echo "  research/recommended_spread_limits.yaml ← recommended costs"
echo "  config/costs.json                       ← active_profile = vantage_measured"
echo "  docs/BACKTEST_RESULTS.md                ← ST-A2 result at measured costs"
echo "  research/backtest_runs.csv              ← E6 run row appended"
echo "  research/trades.csv                     ← E6 trade rows appended"
echo ""
echo "NEXT STEPS:"
echo "  1. Read docs/BACKTEST_RESULTS.md — find PF_2x at RR=5"
echo "  2. Apply E6 decision table (docs/OPS02_REVISED_GATE.md §E6):"
echo "       PF_2x ≥ 1.05  →  ✅ proceed to E1–E4 execution gate"
echo "       PF_2x 1.00-1.05 →  ⚠️  proceed with monitoring"
echo "       PF_2x < 1.00  →  ❌ STOP — prepare ST_A3_RECOVERY_OPTIONS.md"
echo "  3. Populate docs/BACKTEST_COST_REVALIDATION_REPORT.md"
echo "  4. Add E6 sub-entry to docs/VERDICT_LOG.md under ST-A2"
echo ""
