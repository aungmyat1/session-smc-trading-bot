# Repository Cleanup Summary
# Date: 2026-06-25 | Tasks 1–6 complete

---

## 1. File Count Change

| Metric | Before | After | Delta |
|--------|--------|-------|-------|
| Total files (excl pycache/git) | 711 | 715 | +4 (new docs/READMEs) |
| Files in archive/ | 0 | 365 | +365 moved |
| Active source files | 711 | 350 | −361 removed from active tree |
| Top-level directories | 20 | 19 | −1 (session-smc-trading-bot-updated/ gone) |

---

## 2. Archived Files

### archive/session-smc-trading-bot-updated/ (279 files, 4.2MB)
Stale snapshot of root from before the Dukascopy pipeline was built.
Missing: replay_db.py, build_research_db.py, D2 modules, Parquet data pipeline.
Contains unique docs (PHASE1-G audit series, replay_results/) preserved here.

### archive/Database-F-prototype/ (~70 files, 5.0MB)
External prototype project (was at session_smc/Database F/).
Used np.random.random() for trade simulation.
Incompatible schema. Fully superseded by production pipeline.
Key files removed from active tree:
  - replay_db.py (random simulation, NOT ST-A2 chain)
  - replay_engine_v2.py (hardcoded 58% win rate)
  - generate_smc_features.py (naive 3-bar detection)
  - generate_signals.py (incompatible schema)
  - download_forex_data.py (yfinance M1, not Dukascopy)

### archive/scripts-phase-complete/ (15 scripts)
Completed-phase scripts — research phases E6, Phase-2, OPS-01, EXP01-05:
  build_cost_model.py, check_phase2_completion.py, freeze_phase2_dataset.py,
  export_spread_limits.py, compare_e6_to_baseline.py, run_experiments.py,
  run_e6_revalidation.sh, ops01_preflight.py, ops01_reconnect_test.py,
  daily_spread_report.py, validate_connection.py, configure_metaapi_account.py,
  spread_status.py, fetch_data.py, data_audit.py

### archive/docs-phase-complete/ (21 docs)
Phase documentation now closed:
  E6_*.md (9 docs), OPS01_*.md (9 docs), DATA_AUDIT.md, DEPLOYMENT_CHECKLIST.md

### Deleted (no archive needed)
  data/features/ — empty directory (4KB, no content)

---

## 3. Protected Production Files (zero modifications)

| Component | Files | Status |
|-----------|-------|--------|
| `strategy/session_liquidity/` | 9 | UNCHANGED |
| `session_smc/` (minus Database F) | 7 | UNCHANGED |
| `scripts/replay_db.py` | 1 | UNCHANGED |
| `scripts/backtest_session_liquidity.py` | 1 | UNCHANGED |
| `scripts/build_research_db.py` | 1 | UNCHANGED |
| `scripts/replay_6m.py` | 1 | UNCHANGED |
| `research_db/client.py` | 1 | UNCHANGED |
| `research_db/` Parquet files | 14 | UNCHANGED |
| `core/` | 8 | UNCHANGED |
| `execution/` | 11 | UNCHANGED |
| `adaptive/` | 13 | UNCHANGED |
| `strategies/` | 7 | UNCHANGED |

---

## 4. Dependency Changes

None. Zero production imports were altered. Archive operations used `mv`, not `rm`.
The `session_smc/Database F` directory was not imported by any production module
(confirmed by grep — only the modules in `session_smc/*.py` are imported).

---

## 5. Database Schema Changes (Task 5 additions)

### New tables added to vmassit:

| Table | Purpose |
|-------|---------|
| `research.signals` | Signal warehouse — pre-registered signals with full SMC context |
| `analytics.portfolio_equity` | Portfolio-level equity curve (daily/weekly/monthly) |
| `analytics.walk_forward_results` | OOS walk-forward test results per window |

### Altered tables:

| Table | Added columns |
|-------|--------------|
| `research.trades` | `mae`, `mfe`, `holding_bars`, `spread_cost_r`, `signal_id` |

### New views:

| View | Purpose |
|------|---------|
| `analytics.strategy_correlation` (materialized) | Monthly R-correlation between ST-A2, LondonBreakout, NYMomentum |

### Full schema (8 tables + 1 view):
```
research.replay_runs          — run registry
research.trades               — per-trade results (enhanced: +MAE/MFE)
research.signals              — signal warehouse (NEW)
market.smc_events             — SMC events per run
analytics.daily_equity        — daily equity curve
analytics.strategy_metrics    — per-run strategy summary
analytics.portfolio_equity    — portfolio equity (NEW)
analytics.walk_forward_results — OOS test results (NEW)
analytics.strategy_correlation — correlation view (NEW, materialized)
```

---

## 6. Validation Results

**Test 1 — Import check:** PASS
```
All production imports: OK
  strategy.session_liquidity.session_strategy
  strategy.session_liquidity.session_builder
  session_smc.swing_detector
  session_smc.structure_detector
  research_db.client
```

**Test 2 — DB connection:** PASS
```
DB available: True
Connected: 127.0.0.1:5432/vmassit
```

**Test 3 — ST-A2 replay:** PASS — results IDENTICAL to pre-cleanup baseline
```
Symbol: EURUSD | Period: 2024-01-01 → 2024-12-31
Data:   24,974 M15 bars from Parquet (Dukascopy)

n=14  WR=42.9%  PF_std=0.738  PF_2x=0.621  MaxDD=3.95R

Pre-cleanup:  n=14  WR=42.9%  PF=0.738  ✓ MATCH
Post-cleanup: n=14  WR=42.9%  PF=0.738  ✓ MATCH
```

No dependency break. Pipeline intact.

---

## 7. Recommended Next Development Phase

### Priority 1 — Multi-year Dukascopy Data (unblocks 5yr real-data validation)
```bash
python3 scripts/download_dukascopy.py --pair EURUSD --start 2021-01-01 --end 2023-12-31
python3 scripts/build_timeframes.py
python3 scripts/build_research_db.py --symbols EURUSD --start 2021-01-01 --end 2023-12-31
```
Target: replicate the Phase-0 ST-A2 PASS (n=169, PF_2x=1.025) on real tick data.

### Priority 2 — Signal Warehouse Population
Wire `replay_db.py` to also write to `research.signals` with full SMC context
(h4_bias, sweep_type, fvg_present, d1_bias) during replay. Enables future strategy
iteration as SQL joins on precomputed features.

### Priority 3 — Walk-Forward Framework
Use `analytics.walk_forward_results` table + a new `scripts/walk_forward.py` to run
OOS windows: IS 2yr / OOS 1yr, rolling quarterly. Answers: does ST-A2 hold across
all years, or did 2021-2022 carry the PASS?

### Priority 4 — ST-B Implementation
Trend Pullback setup. Unlocked per VERDICT_LOG §3 after EXP05 FAIL (no ST-A2
filter variant cleared PF_2x > 1.25 AND WR ≥ 40% AND MaxDD < 15R AND n ≥ 100).

### Priority 5 — MAE/MFE Enhancement
Update `replay_db.py` to compute per-trade MAE (maximum adverse excursion) and MFE
(maximum favorable excursion) during forward simulation. Populates the new
`research.trades` columns. Used for: SL optimisation research, trade management
analysis, R-multiple distribution modelling.

---

## Clean Structure (current state)

```
session-smc-trading-bot/
├── archive/                        ← superseded code (30-day hold)
│   ├── README.md
│   ├── session-smc-trading-bot-updated/
│   ├── Database-F-prototype/
│   ├── scripts-phase-complete/
│   └── docs-phase-complete/
├── strategy/session_liquidity/     ← ST-A2 core [PROTECTED]
├── session_smc/                    ← SMC primitives [PROTECTED]
├── research_db/                    ← Parquet features + DB client [PROTECTED]
├── scripts/
│   ├── replay_db.py                ← primary replay [PROTECTED]
│   ├── backtest_session_liquidity.py
│   ├── build_research_db.py
│   ├── replay_*.py                 ← all replay variants
│   ├── replay/README.md            ← target location (pending import refactor)
│   ├── analytics/README.md         ← target location (pending import refactor)
│   └── data/README.md              ← target location (pending import refactor)
├── core/                           ← portfolio + signal routing
├── execution/                      ← broker connectivity
├── adaptive/                       ← shadow/demo engine
├── strategies/adapters/            ← strategy plugins
├── simulator/                      ← lookahead validator
├── monitoring/                     ← Telegram, metrics
├── data/
│   ├── raw/dukascopy/EURUSD/2024/  ← source ticks [PROTECTED]
│   ├── processed/EURUSD/           ← OHLCV Parquet [PROTECTED]
│   └── historical/                 ← CSV fallback
├── research_db/ (Parquet)          ← feature layers
├── research/                       ← EXP05, spread data
├── reports/                        ← generated reports
├── docs/
│   ├── VERDICT_LOG.md              ← canonical [NEVER DELETE]
│   ├── REPOSITORY_AUDIT.md         ← this audit
│   ├── CLEANUP_SUMMARY.md          ← this document
│   └── ...
├── config/                         ← YAML configs
├── tests/                          ← pytest suite
├── logs/                           ← runtime logs
├── CLAUDE.md                       ← agent operational rules
└── vmassit PostgreSQL
    ├── research.replay_runs
    ├── research.trades (+MAE/MFE)
    ├── research.signals            ← NEW: signal warehouse
    ├── market.smc_events
    ├── analytics.daily_equity
    ├── analytics.strategy_metrics
    ├── analytics.portfolio_equity  ← NEW
    ├── analytics.walk_forward_results ← NEW
    └── analytics.strategy_correlation ← NEW (materialized view)
```
