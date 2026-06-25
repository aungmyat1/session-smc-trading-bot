# Historical Data Architecture
# Session & SMC Trading Bot — Institutional Data Pipeline
# Date: 2026-06-25

---

## §1 — Directory Layout

```
data/
  raw/
    dukascopy/
      {SYMBOL}/
        {YEAR}/
          {MONTH:02d}/
            ticks.parquet         ← raw bi5 ticks, one file per month
  processed/
    {SYMBOL}/
      M1.parquet                  ← OHLCV + spread, all years concatenated
      M5.parquet
      M15.parquet
      H1.parquet
      H4.parquet
      D1.parquet
  features/
    sweeps/
      {SYMBOL}.parquet            ← session sweep events
    choch/
      {SYMBOL}.parquet            ← CHoCH events (15M)
    bos/
      {SYMBOL}.parquet            ← BOS events (15M)
    fvg/
      {SYMBOL}.parquet            ← Fair Value Gap events (15M)
    sessions/
      {SYMBOL}.parquet            ← session range events (high/low/mid/classification)
```

---

## §2 — Raw Tick Schema

File: `data/raw/dukascopy/{SYMBOL}/{YEAR}/{MONTH:02d}/ticks.parquet`

| Column | dtype | Description |
|---|---|---|
| timestamp_ms | int64 | UTC epoch milliseconds (absolute, not offset) |
| ask | float32 | Ask price (actual, after price_div applied) |
| bid | float32 | Bid price (actual, after price_div applied) |
| ask_vol | float32 | Ask volume (lots) |
| bid_vol | float32 | Bid volume (lots) |

**Index:** None (integer RangeIndex). Sort by `timestamp_ms` ascending.

**Price divisors per symbol:**
```python
PRICE_DIV = {
    "EURUSD": 100_000,
    "GBPUSD": 100_000,
    "USDJPY": 100_000,
    "XAUUSD": 1_000,   # gold — different divisor
}
```

**Dukascopy bi5 wire format (20 bytes/tick, big-endian):**
```
[4B uint32] ms_offset  — milliseconds since start of hour
[4B uint32] ask_raw    — ask price × price_div (integer)
[4B uint32] bid_raw    — bid price × price_div (integer)
[4B float32] ask_vol
[4B float32] bid_vol
```
The absolute timestamp = `hour_epoch_ms + ms_offset`.

**Parquet settings:** `snappy` compression, row group size 100,000 rows.

---

## §3 — Processed OHLCV Schema

File: `data/processed/{SYMBOL}/{TF}.parquet`

| Column | dtype | Description |
|---|---|---|
| timestamp_utc | datetime64[ns, UTC] | Bar open time |
| open | float64 | Mid open = (ask_open + bid_open) / 2 |
| high | float64 | Mid high = max mid across ticks in bar |
| low | float64 | Mid low = min mid across ticks in bar |
| close | float64 | Mid close = last mid in bar |
| volume | float64 | Sum of (ask_vol + bid_vol) |
| ask_open | float32 | Ask at bar open |
| bid_open | float32 | Bid at bar open |
| spread_avg | float32 | Mean (ask − bid) across all ticks in bar |
| spread_max | float32 | Max spread in bar (for stress test) |
| tick_count | int32 | Number of ticks in bar |

**Index:** `timestamp_utc` (DatetimeIndex).

**Resampling logic:**
- `mid = (ask + bid) / 2`
- open = first mid in bar
- high = max mid
- low = min mid
- close = last mid
- volume = sum(ask_vol + bid_vol)
- ask_open = first ask in bar
- bid_open = first bid in bar
- spread_avg = mean(ask − bid)
- spread_max = max(ask − bid)
- tick_count = count of ticks

**Supported timeframes:** M1, M5, M15, H1, H4, D1

---

## §4 — Feature Event Table Schemas

### sweeps — `data/features/sweeps/{SYMBOL}.parquet`

| Column | dtype | Description |
|---|---|---|
| timestamp_utc | datetime64[ns, UTC] | Bar that completed the sweep |
| session | str | `london` / `new_york` |
| direction | str | `bullish` (low swept) / `bearish` (high swept) |
| sweep_level | float64 | Session H/L that was swept |
| sweep_close | float64 | Close price after sweep (must close back inside) |
| session_high | float64 | Full session high |
| session_low | float64 | Full session low |
| htf_bias | str | `bullish` / `bearish` / `neutral` (from bias_filter) |

### sessions — `data/features/sessions/{SYMBOL}.parquet`

| Column | dtype | Description |
|---|---|---|
| session_open | datetime64[ns, UTC] | Session open time |
| session_close | datetime64[ns, UTC] | Session close time |
| session | str | `london` / `new_york` |
| session_high | float64 | |
| session_low | float64 | |
| session_mid | float64 | (high + low) / 2 |
| range_pips | float64 | high − low in pips |
| session_type | str | `range` / `trend` |

### fvg — `data/features/fvg/{SYMBOL}.parquet`

| Column | dtype | Description |
|---|---|---|
| timestamp_utc | datetime64[ns, UTC] | Bar that created the FVG |
| direction | str | `bullish` / `bearish` |
| fvg_high | float64 | Top of gap |
| fvg_low | float64 | Bottom of gap |
| fvg_mid | float64 | (fvg_high + fvg_low) / 2 |
| atr_mult | float64 | Displacement candle body / ATR(14) |
| filled | bool | Whether FVG has been filled (set in post-processing) |

### choch / bos — `data/features/{choch,bos}/{SYMBOL}.parquet`

| Column | dtype | Description |
|---|---|---|
| timestamp_utc | datetime64[ns, UTC] | Bar that confirmed CHoCH/BOS |
| direction | str | `bullish` / `bearish` |
| break_level | float64 | Level that was broken |
| lookback_n | int32 | Swing lookback used |

---

## §5 — Data Flow

```
Dukascopy bi5 (LZMA + HTTP)
         │
         ▼
download_dukascopy.py
  ├── decode struct (20 bytes/tick)
  ├── apply price_div
  ├── convert ms_offset → UTC epoch ms
  └── write data/raw/dukascopy/{SYM}/{Y}/{M}/ticks.parquet
         │
         ▼
build_timeframes.py
  ├── read raw tick Parquet month-by-month
  ├── pandas.resample() per TF
  ├── compute mid, spread columns
  └── write data/processed/{SYM}/{TF}.parquet
         │
         ▼
extract_features.py
  ├── read processed M15 + H4
  ├── run session scanner (session.py)
  ├── run sweep scanner (sweep_detector.py debug)
  ├── run FVG scanner (fvg.py)
  ├── run CHoCH/BOS scanner
  └── write data/features/{type}/{SYM}.parquet
         │
         ▼
validate_dataset.py
  ├── check raw tick coverage by month
  ├── check processed TF continuity (no gaps > 1 bar)
  ├── OHLC integrity check (high ≥ max(O,C), low ≤ min(O,C))
  ├── spread anomaly check (spread > 10pip = flag)
  ├── weekend bar check (Sat/Sun rows)
  └── write reports/dataset_validation_report.md
         │
         ▼
replay_parquet.py (adapter)
  └── loads processed/{SYM}/M15.parquet + H4.parquet
      → same interface as existing CSV loaders
      → plugs into backtest_session_liquidity.py unchanged
```

---

## §6 — Resume / Incremental Download Logic

`download_dukascopy.py` checks:
```python
path = data/raw/dukascopy/{sym}/{year}/{month:02d}/ticks.parquet
if path.exists() and parquet_row_count(path) > 0:
    skip  # already downloaded
else:
    download + decode + write
```

Resume is month-granular. A partially-downloaded month must be re-downloaded (LZMA decompresses all-or-nothing).

---

## §7 — Compatibility with Existing CSV Pipeline

`replay_parquet.py` adapter exposes:
```python
def load_m15(symbol: str) -> pd.DataFrame  # columns matching existing CSV format
def load_h4(symbol: str) -> pd.DataFrame
def load_h1(symbol: str) -> pd.DataFrame
```

The existing `backtest_session_liquidity.py` and `replay_6m.py` call these same function signatures — zero changes to backtest code needed.

---

## §8 — Phase-B Constraints (from CLAUDE.md §0)

1. Do NOT download data automatically — `download_dukascopy.py` only runs when explicitly invoked.
2. Do NOT modify live trading logic, execution code, risk controls, or broker integration.
3. Do NOT modify ST-A2 backtest assumptions or signal chain.
4. Never commit secrets (no tokens in any script).
5. `LIVE_TRADING = False` — this pipeline is research-only.

---

*HISTORICAL_DATA_ARCHITECTURE.md | Written 2026-06-25*
