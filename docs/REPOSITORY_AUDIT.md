# Repository Audit — SMC Trading Research Platform
# Date: 2026-06-25 | Auditor: System Architect
# Pre-cleanup state: 886 files / 28 directories

---

## Audit Legend

| Code | Meaning |
|------|---------|
| A    | KEEP — production / validated / actively used |
| B    | ARCHIVE — useful history, not active code |
| C    | DELETE — never (move to archive/, destroy only after 30-day hold) |

---

## §1 — PROTECTED PRODUCTION COMPONENTS (Class A — never touch)

### `strategy/session_liquidity/` — ST-A2 Core Signal Engine

| File | Purpose | Dependents |
|------|---------|-----------|
| `session_strategy.py` | Top-level orchestrator; `run_strategy()` entry point | replay_db.py, replay_2025.py, backtest_session_liquidity.py, run_strategy_demo.py |
| `session_builder.py` | Asian range, session classify, build_asian_range() | All replay scripts, build_research_db.py |
| `bias_filter.py` | 4H+1H HTF bias (HH+HL) | replay_6m.py, dry_run.py, replay_st_a2_d1.py |
| `sweep_detector.py` | Asian range sweep detection | replay_6m.py, dry_run.py |
| `displacement_detector.py` | 1.2×ATR displacement gate | replay_6m.py, dry_run.py |
| `entry_engine.py` | Signal dataclass + SL/TP calc | replay_6m.py, dry_run.py |
| `config.yaml` | ST-A2 canonical parameters (rr=3.0, min_sl_pips=5.0) | session_strategy.py |

**Risk of deletion: CRITICAL — deletes the entire validated signal chain.**

---

### `session_smc/` — SMC Detection Primitives

| File | Purpose | Dependents |
|------|---------|-----------|
| `swing_detector.py` | swing_highs(), swing_lows(), last_swing_*() | build_research_db.py, backtest.py |
| `structure_detector.py` | htf_bias(), atr(), detect_choch(), detect_bos() | build_research_db.py |
| `liquidity_detector.py` | build_session_range(), detect_sweep() | internal use |
| `poi_detector.py` | find_fvg(), check_fvg_retest() | backtest.py |
| `confirmation_entry.py` | generate_signal_A() — full 11-phase chain | backtest.py, replay_setup_a_parquet.py |
| `daily_bias.py` | D1/D2 swing structure + premium/discount | replay_6m.py |
| `daily_context.py` | D1 context gates (bias, location, POI) | replay_st_a2_d1.py |

**Risk of deletion: CRITICAL — breaks backtest.py and research pipeline.**

---

### `research_db/` — Feature Parquet Database

| File / Dir | Purpose | Dependents |
|-----------|---------|-----------|
| `client.py` | psycopg2 wrapper for vmassit PostgreSQL | replay_db.py |
| `candles/` | EURUSD M1/M5/M15/H1/H4/D1 Parquet (6 files) | build_research_db.py output |
| `sessions/` | 521 London+NY sessions | build_research_db.py output |
| `asian_ranges/` | 261 Asian ranges | build_research_db.py output |
| `swings/` | H4+M15 swing highs/lows | build_research_db.py output |
| `structure/` | H4+M15 BOS/CHoCH events | build_research_db.py output |
| `liquidity/` | 841 Asian range sweeps | build_research_db.py output |
| `fvgs/` | 5,668 M15 FVGs (73.7% fill) | build_research_db.py output |

**Risk of deletion: HIGH — rebuilt via `build_research_db.py` but takes ~10min.**

---

### `scripts/` — Active Research & Replay Scripts

| Script | Class | Purpose |
|--------|-------|---------|
| `replay_db.py` | **A** | Primary replay: Dukascopy → ST-A2 → PostgreSQL |
| `backtest_session_liquidity.py` | **A** | Phase-0 gate: 5yr backtest with spread stress |
| `build_research_db.py` | **A** | Builds all 7 feature Parquet layers |
| `replay_6m.py` | **A** | 6-month BASELINE vs D2_COMBINED comparison |
| `replay_2025.py` | **A** | 2025 EURUSD validation run |
| `replay_st_a2_d1.py` | **A** | ST-A2 + D1 context gates trial |
| `replay_setup_a_parquet.py` | **A** | Setup-A 11-phase full chain replay |
| `replay_parquet.py` | **A** | Parquet data adapter for all replay scripts |
| `dry_run.py` | **A** | Single-day gate decision timeline |
| `download_dukascopy.py` | **A** | Dukascopy tick downloader (bi5 → Parquet) |
| `build_timeframes.py` | **A** | Resamples ticks to M1/M5/M15/H1/H4/D1 |
| `backtest.py` | **A** | Full 11-phase backtest using session_smc/ |
| `extract_features.py` | **A** | SMC event extraction to data/features/ |
| `validate_dataset.py` | **A** | Data quality validation |
| `run_strategy_demo.py` | **A** | Strategy demo/shadow execution on Vantage MT5 |
| `run_portfolio.py` | **A** | Multi-strategy portfolio demo runner |
| `health_check.py` | **A** | Demo account health checks |
| `demo_health_check.py` | **A** | Vantage demo-specific health checks |
| `demo_status.py` | **A** | Demo account status dashboard |
| `capture_spreads.py` | **A** | Live spread measurement at killzones |
| `strategy_stats.py` | **A** | Trade log analytics |

| Script | Class | Purpose |
|--------|-------|---------|
| `build_cost_model.py` | **B** | Built E6 cost model (phase complete) |
| `check_phase2_completion.py` | **B** | Phase-2 spread collection gate (complete) |
| `freeze_phase2_dataset.py` | **B** | E6 dataset snapshot (frozen, done) |
| `export_spread_limits.py` | **B** | E6 output export (done) |
| `compare_e6_to_baseline.py` | **B** | E6 vs baseline comparison (done) |
| `run_experiments.py` | **B** | EXP01–05 post-hoc filter testing (done) |
| `run_e6_revalidation.sh` | **B** | E6 revalidation shell wrapper (done) |
| `ops01_preflight.py` | **B** | OPS-01 MetaAPI preflight (30-day run complete) |
| `ops01_reconnect_test.py` | **B** | OPS-01 reconnect test (complete) |
| `daily_spread_report.py` | **B** | Phase-2 daily spread report (complete) |
| `validate_connection.py` | **B** | MetaAPI connection validator (superseded) |
| `configure_metaapi_account.py` | **B** | One-time account config (done) |
| `spread_status.py` | **B** | Phase-2 spread status (complete) |
| `fetch_data.py` | **B** | Early CSV data fetcher (superseded by Dukascopy) |
| `data_audit.py` | **B** | Pre-Dukascopy data audit (done) |

---

### `core/` — Portfolio & Execution Core

| File | Class | Purpose |
|------|-------|---------|
| `signal.py` | **A** | Canonical Signal dataclass |
| `signal_router.py` | **A** | Routes signals through breaker/portfolio |
| `circuit_breaker.py` | **A** | Daily loss / consecutive loss / drawdown guards |
| `portfolio_manager.py` | **A** | Per-symbol position tracking |
| `strategy_registry.py` | **A** | Strategy plugin registry |
| `trade_journal_db.py` | **A** | SQLite trade journal (data/trade_journal.db) |
| `base_strategy.py` | **A** | Abstract base for all strategy adapters |
| `correlation_manager.py` | **A** | Inter-symbol correlation guards |

---

### `execution/` — Broker Connectivity

| File | Class | Purpose |
|------|-------|---------|
| `metaapi_client.py` | **A** | MetaAPI Cloud SDK wrapper |
| `vantage_demo_executor.py` | **A** | Vantage MT5 demo order placement |
| `mt5_connector.py` | **A** | MT5 WebSocket connector |
| `mt5_executor.py` | **A** | MT5 order execution |
| `trade_manager.py` | **A** | Position lifecycle (open/monitor/close) |
| `trade_journal.py` | **A** | Demo trade journaling (JSONL) |
| `trade_logger.py` | **A** | Structured event logger |
| `order_manager.py` | **A** | Order validation + submission |
| `position_sizer.py` | **A** | Lot size from risk% |
| `risk_manager.py` | **A** | Full risk guard stack |
| `demo_risk_manager.py` | **A** | Demo-mode risk limits |

---

### `adaptive/` — Shadow / Demo Execution Engine

| File | Class | Purpose |
|------|-------|---------|
| `run_shadow.py` | **A** | Shadow runner main loop (MetaAPI feed → signals → journal) |
| `engine/regime_detector.py` | **A** | TRENDING/BREAKOUT/RANGING/UNSAFE classification |
| `engine/signal_scorer.py` | **A** | Multi-factor signal quality score |
| `engine/risk_manager.py` | **A** | Adaptive risk sizing |
| `engine/trade_router.py` | **A** | Routes scored signals to execution |
| `execution/demo_executor.py` | **A** | Paper order simulation |
| `simulation/paper_execution.py` | **A** | Paper fill simulation |
| `state/state_store.py` | **A** | Persistent state (redis-compatible) |
| `filters/news_filter.py` | **A** | High-impact news window blackout |
| `journal/trade_journal.py` | **A** | Adaptive engine trade journal |
| `strategies/smc_session_strategy.py` | **A** | Adaptive SMC strategy |
| `strategies/london_breakout_strategy.py` | **A** | London breakout strategy |
| `strategies/ny_momentum_strategy.py` | **A** | NY momentum strategy |
| `config/adaptive_engine.yaml` | **A** | Adaptive engine configuration |

---

### `strategies/` — Strategy Plugin Adapters

| File | Class | Purpose |
|------|-------|---------|
| `adapters/st_a2_adapter.py` | **A** | Wraps ST-A2 into core.Signal (used by run_portfolio.py) |
| `adapters/london_breakout_adapter.py` | **A** | London breakout adapter |
| `adapters/ny_momentum_adapter.py` | **A** | NY momentum adapter |
| `adapters/adaptive_smc_adapter.py` | **A** | Adaptive SMC adapter |
| `adapters/vwap_adapter.py` | **A** | VWAP breakout adapter |
| `shadow_tracker.py` | **A** | Shadow trade tracking across strategies |

---

### `simulator/` — Lookahead Validation

| File | Class | Purpose |
|------|-------|---------|
| `forward_test.py` | **A** | Bar-by-bar feed simulator; guarantees no lookahead |

---

### `monitoring/` — Alerting

| File | Class | Purpose |
|------|-------|---------|
| `telegram.py` | **A** | Telegram fire-and-forget alerter |
| `metrics.py` | **A** | Prometheus-style metrics collector |

---

## §2 — DATA ASSETS

| Path | Class | Size | Purpose |
|------|-------|------|---------|
| `data/raw/dukascopy/EURUSD/2024/` | **A** | ~420MB | Raw bi5 Dukascopy tick files — source of truth |
| `data/processed/EURUSD/` | **A** | ~18MB | OHLCV Parquet (M1/M5/M15/H1/H4/D1) |
| `data/historical/*.csv` | **A** | ~6MB | CSV fallback (EUR/GBP M15/H4/H1) for replay scripts |
| `data/features/` | **C** | 4KB | Empty directory — no content |
| `research_db/` (Parquet) | **A** | ~18MB | Precomputed SMC feature layers |
| `research/e6_dataset_snapshot/` | **B** | ~2MB | E6 cost model dataset snapshot |
| `data/trade_journal.db` | **A** | — | SQLite trade journal |

---

## §3 — DOCUMENTATION

| File | Class | Purpose |
|------|-------|---------|
| `docs/VERDICT_LOG.md` | **A** | Canonical trial log — never delete |
| `docs/SIGNAL_SPEC.md` | **A** | ST-A2 signal spec |
| `docs/BACKTEST_RESULTS.md` | **A** | ST-A2 / ST-A2 confirmation results |
| `docs/ST_A2_CONFIRMATION.md` | **A** | EXP-01 confirmation |
| `docs/BACKTEST_SPEC.md` | **A** | Phase-0 gate specification |
| `docs/AGENT_RULES.md` | **A** | Operational rules |
| `docs/ADAPTIVE_ENGINE_V1.md` | **A** | Adaptive engine design doc |
| `docs/DEPLOYMENT_READINESS.md` | **A** | Demo deployment gate |
| `docs/RISK_SPEC.md` | **A** | Risk parameter spec |
| `docs/EXECUTION_SPEC.md` | **A** | Execution architecture |
| `docs/FORWARD_TEST_VALIDATION.md` | **A** | Lookahead audit result |
| `docs/WALK_FORWARD_RESEARCH_PLAN.md` | **A** | Next phase roadmap |
| `docs/ST_B_RESEARCH_PLAN.md` | **A** | ST-B strategy plan |
| All `docs/OPS01_*.md` | **B** | OPS-01 run complete — archive |
| All `docs/E6_*.md` | **B** | E6 phase complete — archive |
| `docs/BACKTEST_FAILURE_ANALYSIS.md` | **B** | ST-A FAIL root cause (historical) |
| `docs/BACKTEST_COST_REVALIDATION_REPORT.md` | **B** | Historical cost analysis |
| `reports/` (all) | **A** | Generated replay/analysis reports |
| `CLAUDE.md` | **A** | Operational rules for AI agents |
| `LOOKAHEAD_AUDIT.md` | **A** | Root-level lookahead audit |
| `DATA_AUDIT.md` | **B** | Pre-Dukascopy data audit (superseded) |
| `DEPLOYMENT_CHECKLIST.md` | **B** | OPS-01 checklist (complete) |

---

## §4 — ARCHIVE CANDIDATES (do not delete, move to archive/)

### HIGH PRIORITY — Move immediately

| Path | Reason |
|------|--------|
| `session-smc-trading-bot-updated/` (279 files, 4.2MB) | Stale snapshot of root. Missing: build_research_db.py, replay_db.py, Dukascopy pipeline, D2 modules. Root is 6+ months newer. |
| `session_smc/Database F/` (5.0MB) | External prototype with `np.random.random()` simulation. Schema incompatible. Fully superseded by production pipeline. |

### MEDIUM PRIORITY — Archive in next phase (script audit required)

| Path | Reason |
|------|--------|
| `scripts/ops01_*.py` | OPS-01 MetaAPI 30-day run complete |
| `scripts/build_cost_model.py` | E6 phase complete, cost model frozen |
| `scripts/check_phase2_completion.py` | Phase-2 gate passed |
| `scripts/freeze_phase2_dataset.py` | Dataset frozen |
| `scripts/run_experiments.py` | EXP01–05 complete, results in research/ |
| `scripts/fetch_data.py` | Superseded by download_dukascopy.py |
| `docs/E6_*.md` (12 docs) | E6 phase closed |
| `docs/OPS01_*.md` (9 docs) | OPS-01 run closed |
| `data/features/` | Empty directory |

---

## §5 — DEPENDENCY MAP (critical paths)

```
Dukascopy bi5 ticks
  └── scripts/download_dukascopy.py
        └── data/raw/dukascopy/EURUSD/
              └── scripts/build_timeframes.py
                    └── data/processed/EURUSD/*.parquet
                          ├── scripts/build_research_db.py
                          │     └── research_db/{candles,sessions,...}/*.parquet
                          └── scripts/replay_db.py
                                ├── strategy/session_liquidity/ [ST-A2 core]
                                ├── research_db/client.py
                                └── vmassit PostgreSQL
                                      ├── research.replay_runs
                                      ├── research.trades
                                      ├── market.smc_events
                                      ├── analytics.daily_equity
                                      └── analytics.strategy_metrics
```

---

## §6 — VALIDATED BASELINE (do not alter)

```
Run: rdb_20260625T173310_999eea
Symbol: EURUSD | Period: 2024-01-01 → 2024-12-31
Data: Dukascopy Parquet (24,974 M15 bars)
Strategy: ST-A2 v1 (DEFAULT_CONFIG + min_sl_pips=5.0)

Trades: 14 | Wins: 6 | Losses: 8
Win Rate: 42.9%
PF (std 1.4pip): 0.738
PF (2× stress): 0.621
Max DD: 3.95R
London PF: 0.593 | NY PF: 1.785
```

Any cleanup that changes these numbers = dependency break. Stop and investigate.

---

## §7 — NEXT DEVELOPMENT PHASE

1. **Signal Warehouse** (`research.signals`) — Pre-register signals from research_db Parquet joins
2. **Multi-year Dukascopy** — Download 2021–2023 to enable 5yr real-data replay
3. **Walk-Forward Framework** — scripts/replay/ reorganization + year-by-year OOS testing
4. **ST-B Implementation** — Trend Pullback setup (pending ST-A2 optimization FAIL from EXP05)
5. **Enhanced Trade Analytics** — MAE, MFE, holding_time per trade
6. **Portfolio Analytics** — Cross-strategy correlation, combined equity curve
