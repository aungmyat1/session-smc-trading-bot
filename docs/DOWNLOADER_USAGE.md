# Dukascopy Downloader — Usage Guide
# scripts/download_dukascopy.py

---

## Overview

Downloads institutional-grade tick data from Dukascopy's public data feed.
Stores raw ticks as Parquet to `data/raw/dukascopy/{SYMBOL}/{YEAR}/{MM}/ticks.parquet`.

**IMPORTANT — DO NOT auto-run.** This script is research tooling only.
Running it consumes significant bandwidth (~50–200MB per symbol-month).
Invoke only when explicitly downloading a new date range.

---

## Prerequisites

```bash
pip install aiohttp pyarrow
```

---

## Basic Usage

```bash
# Download EURUSD 5 years (2021–2026)
python scripts/download_dukascopy.py --symbols EURUSD --start 2021-01 --end 2026-06

# Download both symbols
python scripts/download_dukascopy.py --symbols EURUSD GBPUSD --start 2021-01 --end 2026-06

# Check what would be downloaded (no actual download)
python scripts/download_dukascopy.py --symbols EURUSD --start 2021-01 --end 2021-03 --dry-run

# Re-download specific months (force overwrites cached)
python scripts/download_dukascopy.py --symbols EURUSD --start 2021-06 --end 2021-06 --force

# Limit concurrent connections (default: 8)
python scripts/download_dukascopy.py --symbols EURUSD --start 2021-01 --end 2021-12 --workers 4
```

---

## Resume Behaviour

The downloader is **month-idempotent**: if a month's Parquet file already exists and has > 0 rows, it is skipped. A fresh run after a partial download resumes from the first missing month.

```
2021-01: 4,823,420 ticks  [EXISTS — SKIP]
2021-02: 4,219,388 ticks  [EXISTS — SKIP]
2021-03: (missing)        [DOWNLOAD]
```

---

## Output Structure

```
data/raw/dukascopy/
  EURUSD/
    2021/
      01/ticks.parquet    # ~4.8M ticks/month typical
      02/ticks.parquet
      ...
    2022/
      01/ticks.parquet
      ...
  GBPUSD/
    2021/
      01/ticks.parquet
```

**Schema per file:**

| Column | Type | Notes |
|---|---|---|
| timestamp_ms | int64 | UTC epoch milliseconds |
| ask | float32 | Ask price (actual value, price_div applied) |
| bid | float32 | Bid price |
| ask_vol | float32 | Ask-side volume |
| bid_vol | float32 | Bid-side volume |

---

## Price Divisors

Dukascopy stores prices as integers multiplied by a divisor:

| Symbol | Divisor | Example wire value | Actual price |
|---|---|---|---|
| EURUSD | 100,000 | 119,000 | 1.19000 |
| GBPUSD | 100,000 | 133,020 | 1.33020 |
| USDJPY | 100,000 | 13,850,000 | 138.50000 |
| XAUUSD | 1,000 | 1,925,000 | 1,925.000 |

XAUUSD uses divisor 1,000 — the code applies `PRICE_DIV[sym]` per symbol.

---

## Bandwidth Estimate

| Symbol | Period | Approximate size |
|---|---|---|
| EURUSD | 1 month | ~80–150 MB compressed download |
| EURUSD | 5 years | ~5–8 GB download → ~3–4 GB Parquet |
| GBPUSD | 5 years | ~4–7 GB download → ~2–3 GB Parquet |

Plan for ~8–12 GB disk usage for EURUSD + GBPUSD (2021–2026).

---

## Supported Symbols

Current: `EURUSD`, `GBPUSD`, `USDJPY`, `XAUUSD`

Add new symbols by extending `PRICE_DIV` and `DUKA_SYM` in the script.

---

## Next Step After Download

```bash
# Build OHLCV timeframes from raw ticks
python scripts/build_timeframes.py --symbols EURUSD GBPUSD

# Validate the dataset
python scripts/validate_dataset.py
```

---

*DOWNLOADER_USAGE.md | Written 2026-06-25*
