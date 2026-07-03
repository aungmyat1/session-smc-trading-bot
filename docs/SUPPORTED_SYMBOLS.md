---
Date: 2026-07-03
Status: Authoritative
Version: 1.0
Updated: 2026-07-03
Owner: Platform Architecture
Authority: Level 6 — Phase specification
Related: 00_Project/TWO_SYSTEM_ARCHITECTURE_TRUTH.md, PROJECT_OBJECTIVE.md, VIRTUAL_DEMO_GUIDE.md
---

# Supported Symbols

`config/symbols.yaml` is the single source of truth for symbol classification, research eligibility, execution eligibility, session model, precision, and market-cost assumptions.

| Symbol | Asset class | Research | Simple Bot execution | Session model | Price model |
|---|---|---:|---:|---|---|
| EURUSD | Forex | Enabled | Existing allowlist | London/New York | Forex pip |
| GBPUSD | Forex | Enabled | Existing allowlist | London/New York | Forex pip |
| XAUUSD | Metals | Enabled | Existing allowlist | London/New York | Metal tick |
| BTCUSDT | Crypto | Enabled | **Blocked** | Crypto 24/7 / UTC | Crypto tick |

BTCUSDT is supported only by the Strategy Engineering Platform for intake, user-supplied historical data, generic feature and signal generation, replay, backtesting with crypto cost assumptions, analytics, virtual demo, evidence, reports, and package validation.

BTCUSDT is not Forex. Forex pip costs and mandatory London/New York sessions must not be applied. Its research policy requires explicit data source, fee, precision, slippage, trading-hours, exchange-type, volatility, and funding assumptions. The current data-source mode is offline user-supplied CSV or Parquet; no exchange connector or API key is configured.

The Simple Trading Bot rejects packages containing BTCUSDT because it is not in `enabled_execution_symbols`. `live_execution_allowed` is false for every current symbol, and repository-wide live trading remains disabled. Adding BTCUSDT to execution requires a separately approved package, explicit owner decision, execution qualification, and a distinct change to the execution allowlist.
