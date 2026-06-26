# Research Artifacts

This directory stores research outputs, intermediate analysis, and strategy
evaluation artifacts.

## What belongs here

- spread capture summaries
- cost model outputs
- live-vs-backtest comparisons
- execution quality analytics
- holdout and verdict reports
- experiment notes and recommendation documents

## What does not belong here

- broker connection code
- order routing
- position management
- risk execution logic

Those live under `execution/` or `bot.py`.

## Current pattern

Research scripts should produce versioned artifacts that can be queried later,
preferably backed by PostgreSQL or Parquet when possible.

Key examples:

- `research/analyze_spreads.py`
- `research/execution_analyzer.py`
- `research/live_trade_analyzer.py`
- `research/live_vs_backtest_validator.py`
- `research/logger.py`

