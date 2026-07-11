# Professional 3-Year Dataset Plan

Date: 2026-07-11
Status: Implementation runbook

## Objective

Build a frozen, repeatable, 3-year research dataset for:

- EURUSD
- GBPUSD
- BTCUSD
- XAUUSD

The VPS stage is for dataset construction, quality validation, feature extraction,
and first-pass backtests. The MT5-server stage is a later broker-terminal
verification pass against the same exported dataset manifest.

No live trading is enabled by this workflow.

## Stage 1 — VPS

Config:

```bash
config/professional_dataset.yaml
```

Run the full VPS dataset pipeline:

```bash
python3 scripts/run_professional_dataset_pipeline.py --all --workers 4
```

BTCUSD is acquired from Bitget spot candles because Dukascopy BTC ticks are too
slow and flaky for this VPS. The canonical symbol remains `BTCUSD`; source
metadata records the venue pair as `BTCUSDT`. Bitget candles do not include
bid/ask spread, so BTC backtests must apply a separate crypto fee/slippage model.

Acquire BTC directly:

```bash
python3 scripts/download_bitget_candles.py \
  --symbol BTCUSD \
  --source-symbol BTCUSDT \
  --start 2023-07 \
  --end 2026-06 \
  --timeframes M5 M15 H1 H4
```

Progress can be checked with:

```bash
tail -f logs/professional_dataset_download.log
python3 scripts/run_professional_dataset_pipeline.py
```

Run first-pass VPS backtests after the dataset is complete:

```bash
python3 scripts/run_professional_dataset_pipeline.py --backtest --export-mt5
```

Outputs:

```text
reports/dataset_validation_report.md
reports/professional_dataset_manifest.json
artifacts/mt5_dataset_exports/*.tar.gz
features/{SYMBOL}/smc_events.parquet
```

The manifest records file paths, sizes, row counts, and SHA256 hashes for raw
Dukascopy monthly tick files, Bitget BTC raw candle files, and processed
timeframe Parquet files.

## Current State

As of 2026-07-11, EURUSD, GBPUSD, BTCUSD, and XAUUSD have raw and processed
coverage for 2023-07 through 2026-06. BTCUSD is sourced from Bitget spot
`BTCUSDT` candles and stored under the canonical research symbol `BTCUSD`.

The latest validation status is `PASS_WITH_WARNINGS`: no blocking errors, full
coverage, and explicit warnings for unavailable BTC spread data plus FX/XAU
spread/gap observations.

## Stage 1 Backtest Scope

ST-A2 is still pair-specific in `scripts/backtest_session_liquidity.py` and is
valid only for EURUSD/GBPUSD in that runner. Do not force ST-A2 results onto
BTCUSD or XAUUSD.

Any strategy used for BTCUSD/XAUUSD stage-1 evidence must have an adapter that
reads the professional Parquet dataset and a pre-registered trial row in
`docs/VERDICT_LOG.md`.

## Stage 2 — MT5 Server

Transfer the exported package:

```bash
scp artifacts/mt5_dataset_exports/<package>.tar.gz <mt5-server>:/tmp/
```

On the MT5 server:

```bash
mkdir -p ~/professional_dataset
tar -xzf /tmp/<package>.tar.gz -C ~/professional_dataset
```

The MT5-server backtest must verify that the extracted
`reports/professional_dataset_manifest.json` hashes match before running any
broker-terminal strategy test.
