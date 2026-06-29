# Historical Data Audit
# Session & SMC Trading Bot — Phase B Pre-Implementation Audit
# Date: 2026-06-25

---

## §1 — Existing Data Assets

### `data/historical/` — CSV files (existing `fetch_data.py` output)

| File | Rows | Date range | TF | Notes |
|---|---|---|---|---|
| EUR_USD_M15.csv | 121,087 | 2021-06-21 → 2026-06-19 | M15 | Full 5yr coverage |
| EUR_USD_H1.csv  | 30,275  | 2021-06-21 → 2026-06-19 | H1  | Full 5yr coverage |
| EUR_USD_H4.csv  | 7,770   | 2021-06-21 → 2026-06-19 | H4  | Full 5yr coverage |
| GBP_USD_M15.csv | 79,340  | 2023-03-13 → 2026-06-19 | M15 | Starts 2023 — shorter |
| GBP_USD_H1.csv  | 19,819  | 2023-03-13 → 2026-06-19 | H1  | Shorter history |
| GBP_USD_H4.csv  | 5,246   | 2023-03-13 → 2026-06-19 | H4  | Shorter history |

**Total existing rows:** ~264,000 across 6 files.

**Format:** CSV with columns `time, open, high, low, close, volume` (mid-price only — no bid/ask separation).

### `data/raw/`, `data/processed/`, `data/features/` — Empty (created this session)

Directories exist. No data yet.

---

## §2 — Existing Downloader Audit (`scripts/fetch_data.py`)

### Capabilities
- Downloads Dukascopy bi5 tick data (LZMA-compressed, 20-byte records)
- Decodes binary format: `struct.Struct(">IIIff")` — ms_offset, ask×100K, bid×100K, ask_vol, bid_vol
- Resamples to OHLCV at M15, H1, H4
- Caches results as mid-price CSV (`(ask + bid) / 2`)
- Async download with semaphore (10 concurrent)
- Resumes by checking existing CSV row count

### Gaps vs institutional requirements

| Gap | Impact | Fix in new pipeline |
|---|---|---|
| Only 2 symbols (EURUSD, GBPUSD) | Cannot add USDJPY, XAUUSD | Add per-symbol config |
| Output: mid-price only (no bid/ask) | Spread simulation requires separate bid/ask tracks | Store raw ticks with bid/ask columns |
| Storage: CSV (row-per-bar) | Slow for large date scans; no compression | Replace with Parquet |
| No M1/M5 timeframes | Cannot build sub-session micro-structure | Add M1, M5 to resample targets |
| No D1 from raw ticks | D1 is built from H4 by daily_bias.py; low-res | Add D1 from tick resample |
| No validation step | Silent gaps, duplicate bars not caught | `validate_dataset.py` |
| No feature extraction | SMC signals not persisted for cross-symbol studies | `extract_features.py` |
| No raw tick persistence | Cannot re-derive features with new algo | New pipeline saves raw ticks to Parquet |
| CSV cache logic in `fetch_data.py` is ad-hoc | Resume logic fragile | Month-level Parquet partition |

### What to keep
- `_hour_url()` URL logic (month 0-indexed)
- `_TICK` struct format (verified correct)
- `_PRICE_DIV = 100_000.0` for FX pairs
- Async + semaphore pattern
- Session-based caching strategy

---

## §3 — Symbol Coverage Gap

| Symbol | Existing | Required | Notes |
|---|---|---|---|
| EURUSD | Yes (5yr M15/H1/H4) | Yes | Full |
| GBPUSD | Yes (3yr M15/H1/H4) | Yes | 2yr short vs EUR |
| USDJPY | No | Future (cross-pair research) | Not in Phase-0 scope |
| XAUUSD | No | Future (gold session analysis) | Price div = 1,000 (different from FX) |

**Phase-B minimum:** EURUSD + GBPUSD at 5yr (2021-01-01 → 2026-06-19).

---

## §4 — Timeframe Coverage Gap

| TF | Existing | Required | Source |
|---|---|---|---|
| M1  | No | Yes (micro-structure) | Resample from raw ticks |
| M5  | No | Yes (BOS/CHoCH detail) | Resample from raw ticks |
| M15 | Yes (CSV, mid-price) | Yes (Parquet, bid/ask) | Re-derive from raw ticks |
| H1  | Yes (CSV, mid-price) | Yes (Parquet, bid/ask) | Re-derive from raw ticks |
| H4  | Yes (CSV, mid-price) | Yes (Parquet, bid/ask) | Re-derive from raw ticks |
| D1  | No (built from H4 only) | Yes | Resample from raw ticks |

---

## §5 — Feature Persistence Gap

The current pipeline computes SMC signals (sweeps, CHoCH, BOS, FVGs) inside the backtest loop on every run. No persistent feature store exists.

**Impact:**
- Every new trial re-scans 5 years of data
- Cross-symbol analysis requires parallel backtests
- No way to audit signal counts across date ranges without re-running

**Fix:** `extract_features.py` → Parquet event tables in `data/features/`

---

## §6 — Validation Gap

No validation script exists. Known risks from CSV pipeline:
- Weekend bars (Sat/Sun) included in some CSV exports
- Gaps around daylight saving time transitions
- DST-induced duplicates at the 2am–3am UTC boundary
- OHLC integrity (high < open/close in some bars — Dukascopy rounding artifact)
- Volume zeros on thinly-traded hours

---

## §7 — Audit Summary

| Category | Status | Action |
|---|---|---|
| Raw tick storage | MISSING | Create `download_dukascopy.py` with Parquet output |
| Multi-TF coverage | PARTIAL (M15/H1/H4 CSV mid-price) | Create `build_timeframes.py` |
| Bid/ask separation | MISSING | Store ask, bid columns in raw tick Parquet |
| Symbol coverage | PARTIAL (EUR/GBP only) | Extend to USDJPY, XAUUSD (future) |
| GBPUSD 5yr gap | MISSING 2021-2023 | Download via new pipeline |
| Feature persistence | MISSING | Create `extract_features.py` |
| Validation | MISSING | Create `validate_dataset.py` |
| Walk-forward plan | NOT DOCUMENTED | Create `WALK_FORWARD_RESEARCH_PLAN.md` |

---

*HISTORICAL_DATA_AUDIT.md | Written 2026-06-25*
