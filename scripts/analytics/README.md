# scripts/analytics/

Target location for analytics and feature-building scripts.

Planned contents:
  build_research_db.py    — builds all 7 Parquet feature layers
  build_timeframes.py     — resamples ticks to OHLCV timeframes
  extract_features.py     — SMC event extraction
  strategy_stats.py       — trade log analytics

Status: scripts currently live in scripts/ (parent). Move pending import refactor.
