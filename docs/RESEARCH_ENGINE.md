# Research Engine

This repo now includes a separate research-grade pipeline under `src/`:

- `src/data/` for raw candle loading, validation, and parquet storage
- `src/features/` for sessions, swings, structure, liquidity, FVG, and order blocks
- `src/signals/` for reusable signal generation
- `src/backtest/` for a configurable trade simulator
- `src/analytics/` for DuckDB storage and queries

The validated ST-A2 execution path is left untouched.

