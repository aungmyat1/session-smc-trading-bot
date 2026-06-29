# Historical Data Architecture
# Recorded 2026-06-29 | Professional quantitative research data platform standard

Status: Authoritative
Version: 1.0
Updated: 2026-06-29
Owner: Data
Authority: Level 5 — Data Specification
Note: Parquet/DuckDB is authoritative for market and feature data.
PostgreSQL is authoritative for lifecycle control state.
Related: RESEARCH_FEATURE_DATABASE.md, ADR-0001-STABILIZATION-FOUNDATION.md

---

## 1. Architecture Overview

### Purpose

Support multi-asset, multi-strategy portfolio research, deterministic historical
replay, incremental data ingestion, and reproducible backtesting — while remaining
scalable as the platform grows from a single-strategy system to a full research
platform.

### Design Principles

- **Raw data is immutable.** Never modify or overwrite raw vendor files.
- **Features are independent datasets.** No detector modifies OHLC; every detector
  writes its own Parquet layer.
- **Replay never recomputes.** Everything is precomputed and loaded at replay time.
- **Every backtest is reproducible.** Dataset version + feature version + strategy
  version + git commit are recorded together.
- **Parquet is the primary format.** Never use CSV for storage — only for importing
  vendor data.
- **Incremental updates only.** New partitions are appended; historical data is
  never rebuilt.

### Data Lifecycle Layers

```
Raw Data (immutable vendor data)
  ↓
Normalized Data (unified tick schema across all vendors)
  ↓
Market Data (OHLCV bars at all timeframes)
  ↓
Derived Datasets (sessions, structure, liquidity, imbalances, orderflow, confluence)
  ↓
Feature Store (independent, versioned, strategy-aware)
  ↓
Labels (trade outcomes, entry quality, future returns)
  ↓
Strategy Dataset (pre-joined table consumed by each strategy)
  ↓
Replay Dataset (precomputed frames, load-only at replay time)
  ↓
Backtesting Dataset (simulations, portfolios, optimization)
  ↓
Analytics (performance, statistics, equity curves, Monte Carlo)
```

---

## 2. Directory Structure

```
data/
│
├── raw/                           # Immutable vendor data — never modify
│   ├── dukascopy/
│   │   ├── EURUSD/
│   │   │   ├── 2020/
│   │   │   ├── 2021/
│   │   │   └── ...
│   │   ├── GBPUSD/
│   │   ├── USDJPY/
│   │   └── XAUUSD/
│   ├── vantage/
│   ├── mt5/
│   └── other_vendors/
│
├── normalized/                    # Unified tick schema across all vendors
│   ├── tick/
│   │   ├── EURUSD/
│   │   ├── GBPUSD/
│   │   ├── USDJPY/
│   │   └── XAUUSD/
│   └── metadata/
│
├── market/                        # OHLCV bars at all timeframes
│   ├── m1/
│   ├── m5/
│   ├── m15/
│   ├── m30/
│   ├── h1/
│   ├── h4/
│   ├── d1/
│   └── w1/
│
├── sessions/                      # Session-sliced market data
│   ├── london/
│   ├── new_york/
│   ├── asian/
│   └── overlap/
│
├── structure/                     # Market structure features
│   ├── swings/
│   ├── trend/
│   ├── bos/
│   ├── choch/
│   ├── internal_structure/
│   └── external_structure/
│
├── liquidity/                     # Liquidity features
│   ├── equal_highs/
│   ├── equal_lows/
│   ├── liquidity_sweeps/
│   ├── stop_hunts/
│   └── inducements/
│
├── imbalances/                    # Price imbalance features
│   ├── fvg/
│   ├── inverse_fvg/
│   ├── gaps/
│   └── imbalance_clusters/
│
├── orderflow/                     # Order flow and block features
│   ├── order_blocks/
│   ├── breaker_blocks/
│   ├── mitigation_blocks/
│   └── rejection_blocks/
│
├── confluence/                    # Multi-layer confluence features
│   ├── premium_discount/
│   ├── fib_levels/
│   ├── daily_bias/
│   ├── weekly_bias/
│   └── higher_timeframe_context/
│
├── features/                      # Feature store (strategy-aware)
│   ├── strategy_independent/
│   ├── strategy_specific/
│   │   ├── ST_A2/
│   │   ├── London_Breakout/
│   │   ├── NY_Momentum/
│   │   └── Adaptive_SMC/
│   └── ml_features/
│
├── labels/                        # Trade outcomes and quality labels
│   ├── trades/
│   ├── outcomes/
│   ├── entry_quality/
│   ├── risk_reward/
│   └── future_returns/
│
├── replay/                        # Precomputed replay frames — load only
│   ├── candles/
│   ├── ticks/
│   ├── sessions/
│   ├── snapshots/
│   └── playback_cache/
│
├── backtests/                     # Backtest datasets and results
│   ├── datasets/
│   ├── simulations/
│   ├── portfolios/
│   └── optimization/
│
├── analytics/                     # Performance and statistical analysis
│   ├── performance/
│   ├── statistics/
│   ├── equity_curves/
│   ├── drawdowns/
│   ├── monte_carlo/
│   └── reports/
│
├── metadata/                      # Symbol and broker reference data
│   ├── symbols.parquet
│   ├── calendars.parquet
│   ├── trading_sessions.parquet
│   ├── holidays.parquet
│   ├── pip_values.parquet
│   └── spreads.parquet
│
└── cache/                         # Temporary computation cache
```

---

## 3. Storage Standards

### Primary format: Parquet

All stored data is Parquet. Reasons:
- Columnar — reads only the columns needed
- Compressed — smaller than CSV by 5–10×
- Vectorized — DuckDB and Polars operate directly on Parquet
- Native to DuckDB, Polars, and Pandas
- Fast replay — load precomputed frames without recalculation

CSV is only acceptable for importing raw vendor data. Once imported, all data is
converted to Parquet.

### Partitioning Standard

Partition by year and month, not by file-per-symbol.

```
market/m1/EURUSD/year=2025/month=06/part-000.parquet
```

Not:
```
EURUSD_M1.parquet
```

Benefits of partitioning:
- Incremental updates (append new partition only)
- Fast filtering (DuckDB prunes irrelevant partitions)
- Lower memory (load only the time range needed)
- Supports distributed processing later

---

## 4. Data Schemas

### Standard Tick Schema

```
timestamp       datetime (UTC, nanosecond precision)
symbol          string
bid             float64
ask             float64
mid             float64
spread          float64
volume          float64
vendor          string
session         string
```

### Standard Candle Schema (OHLCV)

```
timestamp       datetime (UTC)
symbol          string
timeframe       string
open            float64
high            float64
low             float64
close           float64
tick_volume     int64
real_volume     int64
spread_mean     float64
spread_max      float64
session         string
```

### Feature Dataset Schema

Every detector writes one independent Parquet dataset.

Example path: `features/liquidity_sweeps/EURUSD/year=2025/part-001.parquet`

Example columns (liquidity sweep):
```
timestamp       datetime
symbol          string
direction       string (bullish / bearish)
sweep_price     float64
swing_id        string
session         string
strength        float64
validated       bool
```

Rule: no detector modifies OHLC. Features are separate datasets.

### Strategy Dataset Schema (pre-joined, per strategy)

```
timestamp           datetime
symbol              string
htf_bias            string
bos                 bool
choch               bool
fvg                 bool
sweep               bool
order_block         bool
atr                 float64
session             string
spread              float64
entry               float64
sl                  float64
tp                  float64
outcome             string
```

Each strategy consumes this pre-joined table directly rather than recomputing
features at runtime.

---

## 5. Data Processing Pipeline (Incremental)

```
Download new Dukascopy tick data
  ↓
Normalize to unified tick schema
  ↓
Append to normalized/tick/ partition (new partition only)
  ↓
Generate new candles at all timeframes
  ↓
Update structure, liquidity, imbalance, orderflow, confluence features
  ↓
Update labels
  ↓
Refresh replay cache
  ↓
Ready for backtest
```

No historical data is rebuilt. Only new partitions are processed.

---

## 6. Feature Store Design

Features are **independent, versioned, strategy-aware** Parquet datasets.

- Strategy-independent features (BOS, FVG, liquidity sweeps) are computed once
  and shared by all strategies.
- Strategy-specific features live under `features/strategy_specific/<strategy>/`.
- ML features are a separate layer under `features/ml_features/`.

No feature dataset has a hard dependency on another feature dataset. Each is
computed from OHLC or normalized ticks only.

---

## 7. Replay System Design

Replay never recomputes. Every frame is preloaded from existing datasets.

```
Replay Frame
  ↓
M1 Candle (from market/m1/)
  ↓
Market Structure (from structure/)
  ↓
Liquidity (from liquidity/)
  ↓
FVG (from imbalances/fvg/)
  ↓
Order Block (from orderflow/order_blocks/)
  ↓
Higher TF Bias (from confluence/)
  ↓
Signals (computed from loaded features)
  ↓
Trade Outcome (from labels/)
```

Replay is deterministic because all inputs are frozen Parquet files. The same
dataset version always produces the same replay.

---

## 8. Backtesting and Portfolio Support

```
backtests/
  datasets/      — frozen input datasets per backtest run
  simulations/   — per-strategy simulation results
  portfolios/    — multi-strategy portfolio simulations
  optimization/  — parameter sweep results
```

Multi-strategy portfolio backtests read from the shared feature store —
no per-strategy data rebuild required.

---

## 9. Metadata and Versioning

### Symbol Metadata (stored in metadata/ as Parquet)

- pip size, point value, tick size, digits
- market open / close, DST adjustments, session changes, broker offset
- commission, swap, contract size, leverage

### Dataset Versioning

Every backtest records:

```
dataset_version
feature_version
strategy_version
git_commit
broker
spread_model
commission_model
```

Stored under `dataset_versions/v1/`, `v2/`, etc.
Every historical result is reproducible by restoring the exact dataset version.

---

## 10. Performance and Scalability

### DuckDB Integration

Maintain a lightweight DuckDB catalog that registers Parquet paths as virtual
tables — no data duplication:

```sql
market_m1          → data/market/m1/
market_m15         → data/market/m15/
market_h1          → data/market/h1/
features_liquidity → data/liquidity/liquidity_sweeps/
features_bos       → data/structure/bos/
features_choch     → data/structure/choch/
features_fvg       → data/imbalances/fvg/
labels             → data/labels/
strategy_dataset   → data/features/strategy_specific/
analytics          → data/analytics/
```

Parquet is the single source of truth. DuckDB provides SQL-based research queries
without duplicating storage.

### Scalability Path

| Expansion | How this architecture supports it |
|---|---|
| Additional symbols | Add raw/dukascopy/USDJPY/ — features auto-partition by symbol |
| Multiple brokers | raw/ has separate vendor directories |
| Data vendor comparison | raw/ isolates vendors; normalized/ unifies |
| Machine learning | features/ml_features/ layer already present |
| Portfolio research | backtests/portfolios/ layer already present |
| Hundreds of strategies | strategy_specific/ per strategy; base features shared |

Incremental partitioning means adding a new year of data is an append, not a rebuild.
