# Trading Research Database Architecture

## Overview

Two-layer architecture:

1. **Parquet Data Lake** — Fast, compressed historical market data
2. **PostgreSQL Research DB** — Structured data for trades, events, analytics, experiments

## Layers

- **market**: instruments, candles, smc_events
- **research**: strategies, replay_runs, trades, trade_features, daily_equity
- **analytics**: strategy_metrics, monthly_metrics, optimization_results, experiment_log
- **config**: system configuration

This design supports unlimited historical replay, SMC research, strategy optimization, and future ML integration.