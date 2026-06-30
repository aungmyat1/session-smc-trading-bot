# Testing Report ✅

**Status:** `PASS`  |  **Score:** 92.8  |  **Coverage:** 86.9%
**Generated:** 2026-06-30T06:18:16.303313+00:00  |  **Duration:** 52.284s

## Stage Summary

| Stage | Status | Score | Coverage |
|-------|--------|------:|----------:|
| unit_tests | ✅ PASS | 96.1 | 86.9% |
| integration_tests | ✅ PASS | 83.6 | — |
| strategy_validation | ✅ PASS | 91.7 | — |
| historical_replay | ⏭ SKIP | 100.0 | — |
| regression | ✅ PASS | 100.0 | — |

### integration_tests
- ⚠️ Pipeline stages without dedicated tests: market_data, indicators, session_filter, liquidity_detection, bos, choch, fvg, order_block, risk_engine

### strategy_validation
- ⚠️ KILL_ZONES: Kill zone definition not found in config
- ⚠️ RISK_REWARD: RR not found in config
- ⚠️ MAX_RISK_PER_TRADE: risk_pct not found
- ⚠️ MAX_DAILY_LOSS: max_daily_loss not found
- ⚠️ MARKET_CLOSED_PROTECTION: Market-closed protection not found in config or code
