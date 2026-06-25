# Timeframe Generation Guide
# scripts/build_timeframes.py

---

## Overview

Converts raw tick Parquet → OHLCV bar Parquet at 6 timeframes.
Source: `data/raw/dukascopy/{SYMBOL}/{YEAR}/{MM}/ticks.parquet`
Output: `data/processed/{SYMBOL}/{TF}.parquet`

---

## Usage

```bash
# Build all timeframes for both symbols (default)
python scripts/build_timeframes.py

# Specific symbols and timeframes
python scripts/build_timeframes.py --symbols EURUSD --timeframes M15 H1 H4

# Specific date range (only months in that range are loaded)
python scripts/build_timeframes.py --symbols EURUSD --start 2021-01 --end 2022-12
```

---

## Resampling Logic

For each bar period, ticks are grouped and aggregated:

```python
mid  = (ask + bid) / 2

open  = first mid in bar
high  = max mid across all ticks in bar
low   = min mid across all ticks in bar
close = last mid in bar

volume     = sum(ask_vol + bid_vol)
ask_open   = first ask tick
bid_open   = first bid tick
spread_avg = mean(ask − bid)
spread_max = max(ask − bid)
tick_count = number of ticks
```

The mid-price OHLCV matches the existing CSV pipeline format, making it backward-compatible with all existing backtest scripts.

---

## Output Schema

| Column | Type | Notes |
|---|---|---|
| timestamp_utc | datetime64[ns, UTC] | Bar open time |
| open | float64 | Mid open |
| high | float64 | Mid high |
| low | float64 | Mid low |
| close | float64 | Mid close |
| volume | float64 | Total tick volume |
| ask_open | float32 | Ask at bar open (for spread simulation) |
| bid_open | float32 | Bid at bar open |
| spread_avg | float32 | Mean spread across bar |
| spread_max | float32 | Max spread in bar |
| tick_count | int32 | Ticks in bar |

---

## Supported Timeframes

| Code | Pandas resample freq |
|---|---|
| M1  | `1min` |
| M5  | `5min` |
| M15 | `15min` |
| H1  | `1h` |
| H4  | `4h` |
| D1  | `1D` |

---

## Memory Notes

Building all 6 timeframes for EURUSD 5yr loads ~4B ticks into memory at once (~2–3 GB RAM).
If memory is constrained, process one symbol at a time and use `--start`/`--end` to
process in yearly batches:

```bash
python scripts/build_timeframes.py --symbols EURUSD --start 2021-01 --end 2021-12
python scripts/build_timeframes.py --symbols EURUSD --start 2022-01 --end 2022-12
# etc.
```

The script concatenates all months before resampling. Future optimization: stream-resample
month-by-month (not yet implemented).

---

## Compatibility with Existing Pipeline

The `open/high/low/close` columns in processed Parquet match the CSV format used
by `backtest_session_liquidity.py`, `replay_6m.py`, and `replay_st_a2_d1.py`.

Use `scripts/replay_parquet.py` as a drop-in loader that falls back to CSV if
Parquet is not yet built:

```python
from scripts.replay_parquet import load_m15, load_h4
m15 = load_m15("EURUSD", start="2021-01-01T00:00:00Z")
h4  = load_h4("EURUSD")
```

---

*TIMEFRAME_GENERATION.md | Written 2026-06-25*
