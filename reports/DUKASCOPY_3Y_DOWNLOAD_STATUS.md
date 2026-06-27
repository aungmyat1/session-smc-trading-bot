# Dukascopy 3-Year Tick Data Acquisition Status

Generated: 2026-06-27T11:00:45Z

## Objective

Download and validate exactly the last 3 years of real Dukascopy tick data for:

- EURUSD
- GBPUSD
- XAUUSD

Normalize the result into compressed Parquet with:

- `timestamp`
- `bid`
- `ask`
- `spread`

## What Was Implemented

- Hardened `scripts/download_dukascopy.py` with retry/backoff for 429/5xx responses.
- Added `scripts/normalize_dukascopy_ticks.py` to build a unified tick schema and create the requested dataset tree.
- Created the target folder layout under `data/normalized/`, `data/market/`, `data/sessions/`, `data/structure/`, `data/liquidity/`, `data/imbalances/`, `data/orderflow/`, and `data/confluence/`.
- Confirmed `dukascopy-node` is installed in the user-local npm prefix.

## Environment Check

- Disk: 13 GB free on `/`
- Node.js: `v20.20.2`
- npm: `10.8.2`
- Python: `3.12.3`
- `dukascopy-node`: installed at `~/.local/bin/dukascopy-node`

## Acquisition Progress

### EURUSD

Raw Dukascopy Parquet exists for the full target window under `data/raw/dukascopy/EURUSD/`:

- 2023-07 through 2026-06

### GBPUSD

Raw Dukascopy Parquet exists for the full target window under `data/raw/dukascopy/GBPUSD/`:

- 2023-07 through 2026-06

### XAUUSD

Raw Dukascopy Parquet exists for the full target window under `data/raw/dukascopy/XAUUSD/`:

- 2023-07 through 2026-06

## Validation Status

- Full dataset validation completed successfully after the backfill finished.
- The repo now contains acquisition telemetry sidecars for month-level throughput and retry analysis.

## Verdict

PASS

Reason: the exact last 3-year dataset for all three requested symbols is fully downloaded, normalized, rebuilt into timeframes, and validated.

## Next Step

Optional follow-up:

```bash
python3 scripts/validate_dataset.py --symbols EURUSD GBPUSD XAUUSD --expected-start 2023-07 --expected-end 2026-06
```
