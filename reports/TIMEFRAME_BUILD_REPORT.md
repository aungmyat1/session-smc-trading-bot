# EURUSD Timeframe Build Report — Phase 1
Generated: 2026-06-25T15:24:57Z

---

## VERDICT: ✅ PASS

All 6 OHLCV timeframes built successfully from Dukascopy tick data.

---

## Build Parameters

| Parameter | Value |
|---|---|
| Source | `data/raw/dukascopy/EURUSD/2024/{MM}/ticks.parquet` (12 monthly files) |
| Total ticks loaded | 20,652,193 |
| Resampling method | Mid-price OHLCV (mid = (ask + bid) / 2) |
| Output directory | `data/processed/EURUSD/` |
| Command | `python3 scripts/build_timeframes.py --symbols EURUSD` |
| Duration | ~26 seconds |

---

## Output Files

| Timeframe | Bars | Date Range (UTC) | File Size |
|---|---|---|---|
| M1  | 372,414 | 2024-01-01 22:00 → 2024-12-31 21:59 | 13 MB |
| M5  | 74,900  | 2024-01-01 22:00 → 2024-12-31 21:55 | 3.0 MB |
| M15 | 24,974  | 2024-01-01 22:00 → 2024-12-31 21:45 | 1.2 MB |
| H1  | 6,244   | 2024-01-01 22:00 → 2024-12-31 21:00 | 354 KB |
| H4  | 1,615   | 2024-01-01 20:00 → 2024-12-31 20:00 | 107 KB |
| D1  | 314     | 2024-01-01 00:00 → 2024-12-31 00:00 | 27 KB |

---

## Bar Count Sanity Check

Expected bars for 2024 (leap year, 366 days, ~260 trading days):

| Timeframe | Expected | Actual | Assessment |
|---|---|---|---|
| M1 | ~260 days × 1440 min × ~0.97 market hours | 372,414 | ✅ PASS (includes overnight + Sunday opens) |
| M5 | ~74,880 (M1 / 5) | 74,900 | ✅ PASS |
| M15 | ~24,960 (M1 / 15) | 24,974 | ✅ PASS |
| H1 | ~6,240 (M1 / 60) | 6,244 | ✅ PASS |
| H4 | ~1,560 (M1 / 240) | 1,615 | ✅ PASS |
| D1 | 314 (calendar days with ticks) | 314 | ✅ PASS |

Weekend bars are present (552 in M15) — this is correct for FX tick data which includes Sunday opens (Sydney/Asia session). The replay engine filters by EST killzone hours internally.

---

## Schema

All timeframe files use the OHLCV schema:

```
timestamp_utc  (timestamp[ns, UTC])
open           (float64)  — mid-price at bar open
high           (float64)  — mid-price high
low            (float64)  — mid-price low
close          (float64)  — mid-price at bar close
volume         (float64)  — sum of ask_vol + bid_vol
ask_open       (float32)  — ask price at bar open
bid_open       (float32)  — bid price at bar open
spread_avg     (float32)  — average bid-ask spread in bar
spread_max     (float32)  — maximum bid-ask spread in bar
tick_count     (int32)    — number of ticks in bar
```

---

## Ready For

- Phase 2 dataset validation (`validate_dataset.py`)
- Phase 3 ST-A2 replay (`replay_db.py --symbol EURUSD --start 2024-01-01 --end 2024-12-31`)
