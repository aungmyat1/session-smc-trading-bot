# Session SMC Trading Bot

## What This Project Does

This project is a strategy research and execution-validation system for SMC-style
trading ideas. It is designed to:

- normalize raw market data into a research database
- label sessions, swings, structure, liquidity sweeps, order blocks, and FVGs
- audit a strategy before testing it
- replay the strategy through historical candles
- backtest and stress-test the rules
- validate execution behavior with a virtual broker
- keep demo trading separate from research and live execution
- record the current strategy in the catalog so you can revalidate it safely

In short: it helps you move from an idea to a verified trading setup without
jumping straight into real-market exposure.

## How To Apply It

1. Put the strategy into the catalog in `config/strategy_catalog.yaml`.
2. Mark the strategy you want to validate as the current strategy.
3. Build the research feature database if you need M1-derived features.
4. Run replay, backtest, and virtual-broker validation on the current strategy.
5. Review the validation report and update the strategy rules if needed.
6. Re-run validation until the strategy is ready for demo use.

For the current-strategy revalidation flow, use:

```bash
python3 scripts/run_current_strategy_validation.py --sync-db \
  --replay-json path/to/replay.json \
  --backtest-json path/to/backtest.json \
  --latest-json path/to/latest_metrics.json
```

For the full strategy-validation system, including the audited strategy spec
and the SVOS stages, use:

```bash
python3 scripts/run_current_strategy_svos.py \
  --replay-json path/to/replay.json \
  --backtest-json path/to/backtest.json \
  --robustness-json path/to/robustness.json \
  --demo-json path/to/demo.json
```

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

Revalidate the current strategy without auto-promotion:

```bash
python3 scripts/run_current_strategy_validation.py --sync-db \
  --replay-json path/to/replay.json \
  --backtest-json path/to/backtest.json \
  --latest-json path/to/latest_metrics.json
```

## Validation Workflow

The broader research-to-demo workflow is documented in
[`docs/ESTIMATED_DEVELOPMENT_ROADMAP.md`](docs/ESTIMATED_DEVELOPMENT_ROADMAP.md).
The combined SVOS and EVF operator manual is here:
[`docs/SVOS_EVF_USER_MANUAL.md`](docs/SVOS_EVF_USER_MANUAL.md).

It now includes:

- strategy audit
- rule refinement
- historical replay
- backtest
- robustness tests
- virtual broker validation
- demo validation
- production approval

The recalculated research window before real demo exposure is roughly
11-43 hours, with demo validation still requiring 2-4 weeks of live-market
observation.

## Execution Validation Framework

The Execution Validation Framework, or EVF, checks whether the validated
strategy can execute correctly, safely, and consistently.

It is focused on execution quality, not profitability.

Core checks:

- signal integrity
- order execution
- risk engine behavior
- position sizing and spread handling
- slippage handling
- exit management
- duplicate order protection
- restart recovery
- broker failure handling
- strategy version control

Run EVF against a JSON payload:

```bash
python3 scripts/run_evf.py \
  --payload path/to/execution_payload.json \
  --strategy ST-A2 \
  --period 2023-2026 \
  --rules execution_validation/config/validation_rules.yaml
```

The older direct entrypoint still works:

```bash
python3 scripts/run_execution_validation.py \
  --payload path/to/execution_payload.json \
  --strategy ST-A2 \
  --period 2023-2026 \
  --rules execution_validation/config/validation_rules.yaml
```

Run the replay bridge directly from candle data:

```bash
python3 scripts/run_replay_execution_validation.py \
  --payload path/to/candle_payload.json \
  --strategy ST-A2 \
  --period 2023-2026 \
  --symbol EURUSD \
  --report-dir execution_validation/reports
```

The report is written to:

- `execution_validation/reports/validation_report.json`

An example payload you can run immediately is here:

- `execution_validation/examples/example_execution_payload.json`

The report includes:

- signal accuracy
- order accuracy
- risk accuracy
- spread handling
- slippage statistics
- exit management
- broker simulation status
- final score

Typical result:

- `READY FOR DEMO` when the suite passes
- `BLOCKED` when any critical execution check fails
