# Data Pipeline

**Document:** Historical Data Architecture & Acquisition Pipeline
**Last updated:** 2026-06-30

---

## Overview

Historical OHLCV data is acquired from the Dukascopy public feed via `scripts/fetch_data.py`. Data is stored as Parquet files in `data/`. No live data feed is required for research phases (Phases 0–5).

---

## Data Sources

| Source | Feed Type | Access | Latency |
|--------|-----------|--------|---------|
| Dukascopy | OHLCV tick / M1 aggregated | Public HTTP | Best-effort; no SLA |
| MetaAPI (Vantage) | M15 / H4 live quotes | SDK; requires credentials | Real-time |

Research and backtesting use Dukascopy data only. Live execution uses MetaAPI.

---

## Dataset Specifications

| Symbol | Timeframe | Date Range | Path |
|--------|-----------|------------|------|
| EURUSD | M15 | 2022-01-01 – present | `data/eurusd_m15_*.parquet` |
| GBPUSD | M15 | 2022-01-01 – present | `data/gbpusd_m15_*.parquet` |
| EURUSD | H4 | 2022-01-01 – present | `data/eurusd_h4_*.parquet` |
| GBPUSD | H4 | 2022-01-01 – present | `data/gbpusd_h4_*.parquet` |

---

## Parquet Schema

Each parquet file contains chronological OHLCV candles:

| Column | Type | Description |
|--------|------|-------------|
| `timestamp` | datetime[UTC] | Candle open time in UTC |
| `open` | float64 | Open price |
| `high` | float64 | High price |
| `low` | float64 | Low price |
| `close` | float64 | Close price |
| `volume` | float64 | Tick volume (Dukascopy) |
| `symbol` | str | Trading symbol (EURUSD / GBPUSD) |
| `timeframe` | str | Timeframe (M15 / H4) |

---

## Fetching Data

```bash
# Fetch EURUSD M15 for 2024
python scripts/fetch_data.py --symbol EURUSD --timeframe M15 --year 2024

# Fetch full 3-year dataset
python scripts/fetch_data.py --symbol EURUSD --timeframe M15 --start 2022-01-01 --end 2024-12-31
```

The script downloads hourly Dukascopy tick archives, resamples to the target timeframe, and saves as Parquet.

---

## Data Validation

After fetching, validate dataset integrity:

```bash
python scripts/validate_dataset.py --path data/eurusd_m15_2022_2024.parquet
```

Checks performed:
- No gaps in session hours exceeding 4 hours (excluding weekends)
- No negative spreads (high >= low)
- Timestamps monotonically increasing
- Sufficient row count for phase-3 gates (≥ 50 trades from ≥ 6 months of data)

---

## Data Immutability Rule

**Datasets used in a qualifying trial are frozen.** Once a trial ID is registered in `docs/VERDICT_LOG.md`, the dataset may not be modified. If a dataset update is required, a new trial must be registered.

---

## Multi-Timeframe Alignment

When combining M15 signal data with H4 bias data:
- H4 candle close time is aligned to the M15 grid (H4 candle closes at :00 of each 4-hour boundary)
- M15 candles are labelled with their containing H4 candle
- No lookahead: M15 candle at T can only access the H4 candle that closed at or before T

---

## Storage Layout

```
data/
├── eurusd_m15_2022.parquet
├── eurusd_m15_2023.parquet
├── eurusd_m15_2024.parquet
├── gbpusd_m15_2022.parquet
├── gbpusd_m15_2023.parquet
├── gbpusd_m15_2024.parquet
└── combined/
    ├── eurusd_m15_2022_2024.parquet  (merged 3-year file)
    └── gbpusd_m15_2022_2024.parquet
```
