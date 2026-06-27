# Research Feature Database

This repo now includes a flattened M1 feature pipeline that builds a Parquet table and a DuckDB table from candle data.

## Entry Point

Use:

```bash
python3 run_pipeline.py --symbols EURUSD GBPUSD XAUUSD
```

Optional arguments:

```bash
python3 run_pipeline.py \
  --symbols EURUSD GBPUSD XAUUSD \
  --raw-root data/raw \
  --processed-root data/processed \
  --output-root research_db \
  --swing-lookback 5
```

## Output

The pipeline writes:

- `research_db/data/processed/candles_labeled.parquet`
- `research_db/data/processed/structure.parquet`
- `research_db/data/processed/sweeps.parquet`
- `research_db/data/processed/order_blocks.parquet`
- `research_db/data/processed/fvg.parquet`
- `research_db/feature_database.parquet`
- `research_db/feature_database.duckdb`

## Feature Columns

The final merged table contains:

- `timestamp`
- `pair`
- `open`, `high`, `low`, `close`, `volume`
- `session`
- `swing_high`, `swing_low`
- `structure`
- `bos`, `choch`
- `sweep_high`, `sweep_low`
- `has_order_block`, `ob_type`, `ob_high`, `ob_low`
- `has_fvg`, `fvg_type`, `fvg_high`, `fvg_low`
- `direction`

## Notes

- The pipeline prefers `data/raw` M1 inputs when they exist.
- If raw files are absent, it falls back to processed M1 candles already in the workspace.
- Session labels use UTC hours.
- The current implementation is optimized for reproducibility and research use, not ultra-low-latency production.
