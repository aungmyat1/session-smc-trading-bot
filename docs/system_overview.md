# System Overview

**Platform:** Strategy Engineering Platform (SEP)
**Broker:** Vantage (MT5 Standard, MetaAPI Cloud SDK ≥29)
**Last updated:** 2026-06-30

---

## Purpose

The Strategy Engineering Platform converts a written systematic Forex strategy into a versioned, evidence-backed Production Approval Package — or produces an honest FAIL with findings and a remediation route.

The trading bot is strictly downstream. It executes only strategies that hold a valid, current Production Approval Package.

---

## Supported Instruments

| Symbol | Magic Number | Spread (Standard) | Spread (2x Stress) |
|--------|-------------|-------------------|--------------------|
| EURUSD | 21001 | ~1.0 pip RT | ~2.0 pip RT |
| GBPUSD | 21002 | ~1.5–1.8 pip RT | ~3.0–3.6 pip RT |

---

## Qualification Pipeline Summary

| Phase | Name | Hard Gate |
|-------|------|-----------|
| 0 | Strategy Audit | All critical rules must PASS |
| 1 | Enhancement | Human approval of revised spec |
| 2 | Historical Replay | Zero lookahead; signals inspectable |
| 3 | Backtesting | n ≥ 50, net PF > 1.0 at standard AND 2× spread |
| 4 | Robustness | Walk-forward + Monte Carlo PASS |
| 5 | Virtual Demo | Offline; PnL drift < 10% vs backtest |
| 6 | Production Approval | Out of scope (record only) |

---

## Current Strategy Status

**No strategy is currently active.**

- ST-A2 (Session Liquidity Reversal) is **DEFERRED_REVALIDATION** — preserved but not qualified.
- ST-A: FAIL (2× spread stress failure on GBPUSD)
- EXP05: FAIL (no variant clears all 4 gates)

---

## Key Invariants

1. `LIVE_TRADING=false` and `DEMO_ONLY=true` until owner explicitly changes.
2. Parameter changes are new trials — never mid-trial tuning.
3. All backtest results are net-of-fees. Gross PF is not a result.
4. One position per symbol maximum at any time.
5. Lifecycle mutations flow only through `svos/lifecycle/manager.py`.
6. Governance gate decisions are recorded for every stage transition.

---

## Environment Variables

| Variable | Description | Required for |
|----------|-------------|--------------|
| `VANTAGE_DEMO_METAAPI_ID` | MetaAPI account ID for Vantage demo | Demo execution |
| `VANTAGE_LIVE_METAAPI_ID` | MetaAPI account ID for Vantage live | Live deployment |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token for alerts | Monitoring |
| `TELEGRAM_CHAT_ID` | Telegram chat ID for alert delivery | Monitoring |
| `DATABASE_URL` | PostgreSQL URL (optional; falls back to JSONL) | PG governance backend |
| `LIVE_TRADING` | Set `true` to enable live orders (owner only) | Execution |
| `DEMO_ONLY` | Set `false` only after Production Approval | Execution |
