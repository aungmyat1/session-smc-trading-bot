# Session SMC Trading Bot

## Research Feature Database

Build the M1 research feature database with:

```bash
make research-db
```

That runs:

```bash
python3 run_pipeline.py --symbols EURUSD GBPUSD XAUUSD
```

Outputs:

- `research_db/data/processed/candles_labeled.parquet`
- `research_db/data/processed/structure.parquet`
- `research_db/data/processed/sweeps.parquet`
- `research_db/data/processed/order_blocks.parquet`
- `research_db/data/processed/fvg.parquet`
- `research_db/feature_database.parquet`
- `research_db/feature_database.duckdb`

Focused tests:

```bash
make test-research-db
```

