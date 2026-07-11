# Research DB Schema

`migrations/research_dataset_v2.sql` defines the PostgreSQL research schema for dataset v2:

- `research.market_bars`
- `research.tick_data`
- `research.smc_events`
- `research.market_regimes`
- `research.cost_models`
- `research.data_quality`
- `research.dataset_manifests`

The migration uses idempotent `CREATE IF NOT EXISTS` statements and indexes timestamp-heavy query paths. `scripts/load_dataset_to_research_db.py` currently loads manifest and quality metadata into a local SQLite compatibility target for offline validation; the SQL migration is the production Postgres contract.
