---
Date: 2026-07-03
Status: Approved
Version: 1.0
Updated: 2026-07-03
Owner: Strategy Engineering
Authority: Level 6 — Phase specification
Related: SUPPORTED_SYMBOLS.md, READINESS_CRITERIA.md, HISTORICAL_REPLAY.md
---

# Virtual Demo Guide

Virtual demo is an offline Strategy Engineering Platform qualification stage. It does not connect to Vantage or any cryptocurrency exchange.

For BTCUSDT:

1. Supply UTC M1 candles as CSV or Parquet with timestamp, open, high, low, close, and optional volume.
2. Validate the symbol through `config/symbols.yaml` and validate candle chronology before replay.
3. Use `Crypto24h` or `UTC` session identity. Do not force London/New York filters.
4. Use basis-point fee, slippage, and stop-buffer assumptions from the crypto research policy and calibrate them to the dataset.
5. Record whether the dataset represents spot or perpetual markets. A perpetual dataset requires a funding-cost model before qualification.
6. Produce replay, backtest, analytics, virtual-demo, and risk evidence before package approval.

A BTCUSDT package may be produced as research evidence, but the Simple Trading Bot rejects it while BTCUSDT is absent from `enabled_execution_symbols`. Live trading remains disabled.
