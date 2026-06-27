# Database Architecture Verification

Date: 2026-06-27

This note verifies the current database implementation against the attached
target architecture for a professional quantitative research platform.

## Verified In This Repo

### PostgreSQL research schema

The repository already defines a structured PostgreSQL schema in
[`db/schema_v2.sql`](/home/aungp/session-smc-trading-bot/db/schema_v2.sql):

- `market`
- `research`
- `analytics`
- `config`

It includes the core tables needed for research operations:

- instruments
- candles
- Asian session ranges
- session ranges
- SMC events
- strategies
- replay runs
- trades
- trade features
- daily equity
- strategy metrics
- monthly metrics
- optimization results
- phase-0 gate verdicts
- system config

### Feature store / research dataset

The repo also has a DuckDB-backed feature database in
[`src/research_feature_database.py`](/home/aungp/session-smc-trading-bot/src/research_feature_database.py).

It builds and stores:

- `candles_labeled`
- `structure`
- `sweeps`
- `order_blocks`
- `fvg`
- `feature_database`

Outputs are written under `research_db/`.

### Layer scaffold and verifier

The repo now includes an explicit layered data scaffold under `data/`:

- `data/layers_manifest.json`
- `data/labels/`
- `data/replay/`
- `data/backtests/`
- `data/analytics/`
- `data/metadata/`
- `data/cache/`

The automated verifier is:

- [`scripts/verify_data_layers.py`](/home/aungp/session-smc-trading-bot/scripts/verify_data_layers.py)

It checks:

- required layer directories
- raw tick Parquet schema
- normalized tick Parquet schema
- processed OHLCV Parquet schema
- freshness windows

### Bootstrap and verification

The database bootstrap script now runs in dry-run mode correctly:

```bash
python3 scripts/bootstrap_quant_db.py --dry-run
```

That confirms the schema file is reachable and the script is self-contained when
invoked directly.

### Test verification

Focused database-related tests passed:

- `tests/research_engine/test_feature_database.py`
- `tests/test_validate_dataset.py`
- `tests/core/test_trade_journal_db.py`

Result:

- `29 passed`

Layer verifier result:

- `PASS`

## Match To The Proposed Architecture

The current repo matches the proposed design in these ways:

- It separates raw/processed research inputs from relational analytics.
- It stores a canonical SQL schema for research, analytics, and config data.
- It persists derived research features into a columnar analytics store.
- It supports reproducible replay and backtest-oriented datasets.

## Partial Matches

These parts exist, but not as fully separate top-level lifecycle layers yet:

- raw data
- normalized data
- labels
- replay datasets
- backtesting datasets
- metadata snapshots
- version control / dataset lineage

The repo has some of these concepts, but not as a fully standardized folder
hierarchy like the one in the design note.

## Gaps Relative To The Target Design

The attached architecture suggests a larger platform than the current repo
implements today:

- dedicated vendor-specific raw storage for multiple brokers/data vendors
- explicit year/month partitioning for all market data layers
- fully separated labels, replay, backtest, and analytics layers
- broader metadata tables for calendars, holidays, sessions, spreads, and pip values
- stronger dataset lineage/versioning for every research artifact

## Verification Summary

Status:

- `database schema`: PASS
- `feature store build path`: PASS
- `bootstrap script direct execution`: PASS after fix
- `full target architecture`: PARTIAL

Conclusion:

The repo already has a solid research database foundation, but the attached
design describes a more mature institutional data platform. The implementation
here is a good step toward that target, not yet the full target state.
