# pipeline — Phase-0 Backtest Pipeline

Date: 2026-06-29
Status: Authoritative
Version: 1.0
Updated: 2026-06-29
Owner: Platform / Quant Research
Authority: Level 6 — Module Documentation
Related: docs/03_Pipeline_Stages/HISTORICAL_REPLAY.md, docs/BACKTEST_SPEC.md,
         docs/VERDICT_LOG.md

---

## Purpose

This package orchestrates the Phase-0 backtest gate for ST-A2 (Session Liquidity
Reversal — Sweep Reversal strategy). It runs a deterministic, net-of-fees replay
against historical OHLCV Parquet data for EURUSD and GBPUSD, evaluates the Phase-0
pass/fail gate under both standard and 2× spread stress scenarios, and persists all
results to PostgreSQL.

The pipeline enforces the platform's hard research rules: every cost is deducted
before computing profit factor, no future data is accessible during replay, and all
results are written to a database so that findings are reproducible and auditable.

---

## Architecture

The pipeline runs in four sequential stages driven by `run_phase0.py`:

```
config.py               Single source of truth for all parameters and cost models
       |
       v
pipeline_02_build_features.py
  Reads raw OHLCV Parquets → derives Asian range, session ranges, raw signal audit
  Writes: data/features/{SYMBOL}/asian_range.parquet
          data/features/{SYMBOL}/session_range.parquet
          data/features/{SYMBOL}/signals_audit.parquet
       |
       v
pipeline_03_replay_engine.py
  Loads feature Parquets + M1/M15 OHLCV → runs deterministic bar-by-bar replay
  Applies full 11-phase AND-gate signal logic (generate_signal_A)
  Simulates trade outcomes via M1 walk-forward (no random outcomes)
  Runs both standard and 2× spread stress in one pass
  Writes: data/features/{SYMBOL}/replay_trades_{scenario}.parquet
          data/features/{SYMBOL}/replay_summary_{scenario}.parquet
       |
       v
pipeline_04_write_db.py
  Loads replay Parquets → writes normalised rows to PostgreSQL
  Tables: research.strategies, research.replay_runs, research.trades,
          research.trade_features, research.daily_equity,
          analytics.strategy_metrics, analytics.monthly_metrics,
          analytics.phase0_gate
       |
       v
Gate verdict printed to stdout
  n >= 50  AND  net PF > 1.0  at BOTH standard AND 2× stress  →  PASS
  Otherwise  →  FAIL
```

---

## Module Inventory

| Module | Purpose |
|---|---|
| `config.py` | Single source of truth for pipeline parameters: spread configs (standard + 2× stress), session windows (Asian 00-07, London 07-10, NY 13-16 UTC), signal chain parameters (swing_n, SL sizing, TP R-multiples, D2 context gates), Phase-0 gate thresholds, symbol list, and filesystem paths |
| `pipeline_02_build_features.py` | Pre-computes derived feature Parquets from raw OHLCV: Asian session H/L/mid, London and NY session ranges with type classification, and a raw signals audit file. Uses `session_smc.liquidity_detector` for range and session classification. |
| `pipeline_03_replay_engine.py` | Deterministic bar-by-bar replay engine. Loads M15 candles for signal detection and M1 candles for trade outcome simulation. Applies the full 11-phase AND-gate via `generate_signal_A`. Applies net-of-fees P&L (spread + commission), TP1/TP2 partial-close logic (75% at 4R, runner to 5R, SL to BE), and session-end auto-close. Supports standard and 2× spread stress scenarios. |
| `pipeline_04_write_db.py` | PostgreSQL writer. Loads replay result Parquets from `data/features/` and writes them into the research and analytics schemas using SQLAlchemy. Builds the daily equity curve and computes the phase0_gate verdict row. Requires `DATABASE_URL` in the environment; skip with `--skip-db` for dry runs. |
| `run_phase0.py` | End-to-end orchestrator. Parses CLI arguments, calls each pipeline stage in order, prints the final gate verdict. Accepts `--symbol`, `--start`, `--end`, `--skip-features`, and `--skip-db` flags. |

---

## Inputs

| Input | Location | Notes |
|---|---|---|
| Raw OHLCV Parquets | `data/processed/{SYMBOL}/{SYMBOL}_{TF}.parquet` | Required timeframes: M1 (for trade simulation), M15 (for signal detection). Filename variants `{SYMBOL}_{TF}_raw.parquet` are also accepted. |
| Pipeline configuration | `pipeline/config.py` | All parameters are read from this module; no external config files. |
| PostgreSQL connection | `DATABASE_URL` environment variable | Required only when writing results. Resolved via `db.runtime.resolve_database_url()`. |

---

## Outputs

| Output | Location | Description |
|---|---|---|
| Asian range features | `data/features/{SYMBOL}/asian_range.parquet` | Daily Asian session H/L/mid (00-07 UTC) |
| Session range features | `data/features/{SYMBOL}/session_range.parquet` | London + NY session H/L/mid/type per day |
| Raw signal audit | `data/features/{SYMBOL}/signals_audit.parquet` | Signal detections with no trade outcome, for inspection |
| Replay trades | `data/features/{SYMBOL}/replay_trades_{scenario}.parquet` | Per-trade records including net-of-fees P&L and SMC feature flags |
| Replay summary | `data/features/{SYMBOL}/replay_summary_{scenario}.parquet` | Aggregate metrics (PF, WR, DD) per symbol per scenario |
| PostgreSQL tables | `research.*`, `analytics.*` schemas | Strategies, runs, trades, features, equity curve, metrics, gate verdict |
| Gate verdict | stdout | PASS / FAIL per symbol per scenario, printed at the end of the run |
| Reports | `reports/` | Pipeline may write supplementary report files here |

---

## Lifecycle Role

This pipeline produces research evidence for the STATISTICAL_VALIDATION stage of the
SVOS pipeline (`DRAFT → AUDIT → REFINEMENT → HISTORICAL_REPLAY → STATISTICAL_VALIDATION
→ ...`). The Phase-0 gate verdict — passing both standard and 2× spread stress with
n >= 50 trades and net PF > 1.0 — is the minimum evidence required to advance a
strategy to ROBUSTNESS_VALIDATION.

Output must be recorded in `docs/VERDICT_LOG.md` with the trial ID before the run.
Every parameter change requires a new trial ID. Never reuse a trial ID.

---

## Configuration

All parameters live in `pipeline/config.py`. Key values:

| Parameter | Value | Notes |
|---|---|---|
| `SPREAD_STANDARD["EURUSD"]` | 0.8 spread + 0.6 commission pips | Vantage Standard account |
| `SPREAD_STANDARD["GBPUSD"]` | 1.2 spread + 0.6 commission pips | Vantage Standard account |
| `SPREAD_STRESS_2X["EURUSD"]` | 1.6 spread + 0.6 commission pips | Required stress gate |
| `SPREAD_STRESS_2X["GBPUSD"]` | 2.4 spread + 0.6 commission pips | Required stress gate |
| `SESSIONS` | London 07-10 UTC, NY 13-16 UTC | Signal detection windows |
| `ASIAN_WINDOW` | 00-07 UTC | Range that London sweeps |
| `SIGNAL_CONFIG["tp1_r"]` | 4.0 | TP1 closes 75% of position |
| `SIGNAL_CONFIG["tp2_r"]` | 5.0 | TP2 runner target |
| `SIGNAL_CONFIG["sl_range_pct"]` | 0.25 | SL = 25% of session range |
| `SIGNAL_CONFIG["sl_buffer_pips"]` | 3.0 | Buffer beyond wick extreme |
| `PHASE0_MIN_TRADES` | 50 | Minimum trades for a valid gate |
| `PHASE0_MIN_NET_PF` | 1.0 | Minimum net profit factor (both scenarios) |
| `SYMBOLS` | EURUSD, GBPUSD | Symbols processed by default |

Do not change any parameter without pre-registering a new trial ID in
`docs/VERDICT_LOG.md` first.

---

## Running

Full run (both symbols, 2020-2025):

```bash
python -m pipeline.run_phase0 --start 2020-01-01 --end 2025-01-01
```

Single symbol:

```bash
python -m pipeline.run_phase0 --symbol EURUSD --start 2022-01-01 --end 2025-01-01
```

Dry run (no PostgreSQL required):

```bash
python -m pipeline.run_phase0 --start 2020-01-01 --end 2025-01-01 --skip-db
```

Skip feature rebuild (use cached Parquets from a previous run):

```bash
python -m pipeline.run_phase0 --start 2020-01-01 --end 2025-01-01 --skip-features
```

Individual stages can also be run directly for debugging:

```bash
python -m pipeline.pipeline_02_build_features --symbol EURUSD
python -m pipeline.pipeline_03_replay_engine --all --stress
python -m pipeline.pipeline_04_write_db
```

---

## Limitations

- **EURUSD and GBPUSD only.** The symbol list is fixed in `config.py`; other pairs
  are not supported without code changes and a new trial registration.
- **M1 and M15 Parquets required.** The replay engine depends on both timeframes.
  Missing M1 data causes the trade simulation step to fail for that symbol.
- **No sandbox.** Results are written directly to the configured PostgreSQL instance.
  Use `--skip-db` to avoid database writes during development or when no DB is
  available.
- **Feature cache is not date-scoped.** Running with `--skip-features` reuses cached
  feature Parquets regardless of the `--start`/`--end` dates. Rebuild features
  whenever the date range changes.
- **Signal logic is not configurable at runtime.** All signal chain parameters are
  in `config.py`. Changes require editing the file and registering a new trial.

---

## Important: Trial Registration

This pipeline MUST NOT be run without a pre-registered trial ID in
`docs/VERDICT_LOG.md`. This is a hard rule from CLAUDE.md §2. Changing
parameters and re-running under the same trial ID destroys reproducibility.

Steps before every run:

1. Add a new row to `docs/VERDICT_LOG.md` with the trial ID, date, symbol(s),
   date range, and all parameter values that differ from the previous trial.
2. Record the trial ID in the run (the DB write includes it in `research.replay_runs`).
3. After the run, record the gate verdict (PASS / FAIL) in the same row.

A single-spread PASS is not sufficient. The trial must pass both standard and 2×
spread stress to advance.
