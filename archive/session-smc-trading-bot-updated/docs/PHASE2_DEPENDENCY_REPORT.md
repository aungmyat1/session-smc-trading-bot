# PHASE 2 — DEPENDENCY REPORT
# Session SMC Trading Bot (Updated) — Missing Dependencies Classification
**Date:** 2026-06-25 | **Status:** Post-fix

---

## CLASSIFICATION KEY
- 🔴 CRITICAL — Blocks startup / causes immediate crash
- 🟠 HIGH — Breaks specific runner / major feature unavailable
- 🟡 MEDIUM — Degrades non-critical functionality
- 🟢 LOW — Test coverage gap / cosmetic

---

## DEPENDENCIES FOUND MISSING (PRE-FIX)

| # | File | Purpose | Severity | Fix Applied |
|---|------|---------|----------|-------------|
| 1 | `data/__init__.py` | Package marker for data module | 🔴 CRITICAL | ✅ Copied from prod |
| 2 | `data/session_filter.py` | London/NY session detection used by bot.py line 84 | 🔴 CRITICAL | ✅ Copied from prod |
| 3 | `data/forex_data.py` | OHLCV fetcher (MetaAPI historical candles) | 🔴 CRITICAL | ✅ Copied from prod |
| 4 | `data/historical/` | EURUSD/GBPUSD M15+H4 CSV files (2021–2026) | 🔴 CRITICAL | ✅ Symlinked to prod |
| 5 | `adaptive/data/__init__.py` | Package marker for adaptive data module | 🟠 HIGH | ✅ Copied from prod |
| 6 | `adaptive/data/market_feed.py` | Market feed adapter for shadow runner | 🟠 HIGH | ✅ Copied from prod |
| 7 | `scripts/run_portfolio.py` | Multi-strategy portfolio runner | 🟡 MEDIUM | Not needed for ST-A2 demo phase |
| 8 | `tests/portfolio/` | Portfolio runner test suite | 🟢 LOW | Not needed for deployment |
| 9 | `data/adaptive_state.json` | Persistent adaptive engine state | 🟢 LOW | Created at runtime |
| 10 | `data/trade_journal.db` | SQLite trade journal | 🟢 LOW | Created at runtime |

---

## POST-FIX STATUS

### CRITICAL (all resolved)
```
data/session_filter.py       ✅ RESOLVED — copied
data/forex_data.py           ✅ RESOLVED — copied
data/historical/EUR_USD_M15.csv   ✅ RESOLVED — symlinked (121,086 bars, 2021–2026)
data/historical/EUR_USD_H4.csv    ✅ RESOLVED — symlinked (30,269 bars)
data/historical/GBP_USD_M15.csv   ✅ RESOLVED — symlinked (79,339 bars, 2023–2026)
data/historical/GBP_USD_H4.csv    ✅ RESOLVED — symlinked (19,834 bars)
```

### HIGH (all resolved)
```
adaptive/data/market_feed.py  ✅ RESOLVED — copied
```

### MEDIUM (accepted, not blocking demo)
```
scripts/run_portfolio.py      ⚠️ ACCEPTED — ST-A2 demo uses bot.py + run_st_a2_demo.py
```

### LOW (auto-generated at runtime)
```
data/adaptive_state.json      ⚠️ ACCEPTED — created when adaptive engine first runs
data/trade_journal.db         ⚠️ ACCEPTED — TradeLogger creates on first write
```

---

## REMAINING GAPS (non-blocking)

### XAUUSD historical data
- `data/historical/XAU_USD_M15.csv` — NOT available anywhere on the system
- Phase 7 replay will be EURUSD only (XAUUSD cannot be backtested)
- Status: 🟡 MEDIUM — not blocking ST-A2 demo (demo.yaml lists XAUUSD but data is absent)
- Recommendation: Add XAUUSD data before enabling XAUUSD in demo

### scripts/ directory
- Updated bot has no `scripts/` directory
- All script runners (run_st_a2_demo.py, health_check.py, dry_run.py) exist in current bot only
- Status: 🟡 MEDIUM — bot.py works as main entry point; scripts are helpers
- Recommendation: Copy relevant scripts in Phase 5 fix if needed

---

## DEPENDENCY SUMMARY

| Category | Total Found | Resolved | Remaining |
|----------|-------------|----------|-----------|
| CRITICAL | 6 | 6 | 0 |
| HIGH | 2 | 2 | 0 |
| MEDIUM | 2 | 0 | 2 (accepted) |
| LOW | 2 | 0 | 2 (auto-generated) |
| **TOTAL** | **12** | **8** | **4 (non-blocking)** |

**Deployment blocker count after fix: 0**
