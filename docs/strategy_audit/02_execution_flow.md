# Execution Flow

## Portfolio Runner

`scripts/run_portfolio.py` is the live portfolio orchestration path for the multi-strategy bot.

1. Load `config/strategy_portfolio.yaml`.
1. Register adapters for `ST-A2`, `LondonBreakout`, `NYMomentum`, `AdaptiveSMC`, `VWAPMeanReversion`, and `VWAPBreakout`.
1. Fetch `M15` data for all routed symbols and `H4` data for strategies that need higher-timeframe context.
1. Reject symbols when spread exceeds the per-symbol cap.
1. Call each registered strategy adapter with its symbol list and config.
1. Tag the resulting `core.Signal` objects with execution mode.
1. Send signals through `SignalRouter`.
1. Apply `CircuitBreaker` checks per strategy.
1. Apply `PortfolioManager` checks for confidence, correlation, trade count, and open-position caps.
1. Route approved signals to the execution stack or shadow tracker.

## D2E3 Runner

`scripts/run_d2_e3_demo.py` is a separate standalone runner.

1. Load `D2E3Params`.
1. Maintain one `D2E3Engine` instance per symbol.
1. Process bars incrementally and keep engine state between polls.
1. Emit setup, confirmation, fill, and close events into the trade journal.
1. Synchronize the journal into the research database through the D2E3 ingest path.

## Signal Lifecycle

`core.Signal` carries the execution contract for the portfolio path:

- `timestamp`
- `strategy_name`
- `symbol`
- `action`
- `entry_price`
- `stop_loss`
- `take_profit`
- `risk_percent`
- `confidence`
- `ttl_seconds`
- `metadata`

Signals expire after `ttl_seconds` seconds. The current canonical default is `300`.

