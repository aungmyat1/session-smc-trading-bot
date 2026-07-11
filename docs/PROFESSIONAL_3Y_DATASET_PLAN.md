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

BTCUSD is heavier than FX/XAUUSD on Dukascopy and should be acquired with a
slower, resume-safe command:

```bash
nohup python3 scripts/run_professional_dataset_pipeline.py \
  --download-missing \
  --workers 1 \
  --timeout-seconds 120 \
  --max-retries 10 \
  > logs/professional_dataset_download.log 2>&1 &
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
monthly tick files and processed timeframe Parquet files.

## Current Gap

As of this runbook, EURUSD, GBPUSD, and XAUUSD raw/processed coverage exists for
2023-07 through 2026-06. BTCUSD is the missing fourth symbol and must be fetched
before the four-symbol dataset can be frozen.

The pipeline reports missing raw months before download. This is expected until
BTCUSD acquisition completes.

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
