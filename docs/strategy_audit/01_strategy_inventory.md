# Strategy Inventory

This audit covers the runtime strategy surfaces that are actually present in the bot today.

## Deployable And Shadow Strategies

| Strategy | Runtime name | Catalog status | Execution mode | Symbols | Timeframes | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| ST-A2 | `ST-A2` | `demo` / approved | `demo` | `EURUSD`, `GBPUSD`, `XAUUSD` in portfolio config | `M15`, `H4` | Core session-liquidity strategy; adapter emits canonical `core.Signal`.
| London Breakout | `LondonBreakout` | `research` | `demo` | `EURUSD`, `GBPUSD`, `XAUUSD` in portfolio config | `M15` | Asian range breakout with London retest.
| NY Momentum | `NYMomentum` | `replay` | `demo` | `EURUSD`, `GBPUSD`, `XAUUSD` in portfolio config | `M15` | NY sweep of London levels with retest.
| Adaptive SMC | `AdaptiveSMC` | `research` | `shadow` | `EURUSD`, `GBPUSD` in catalog, portfolio config also routes `XAUUSD` | `M15`, `H4` | Wrapper around the ST-A2 session chain; signal-only in portfolio.
| VWAP Mean Reversion | `VWAPMeanReversion` | `shadow` | `shadow` | `EURUSD`, `GBPUSD`, `XAUUSD` | `M15` | Session-scoped VWAP fade with sweep + reclaim.
| VWAP Breakout | `VWAPBreakout` | `shadow` | `shadow` | `EURUSD`, `GBPUSD`, `XAUUSD` | `M15` | Compatibility alias for `VWAPMeanReversion`.
| D2E3 | `D2E3` | `research` | standalone demo runner | `EURUSD`, `GBPUSD` | `M15` | Separate stateful PDH/PDL sweep + MSS branch; not wired into portfolio runner.

## Internal Strategy Surfaces

| Surface | Purpose | Notes |
| --- | --- | --- |
| `strategy.session_liquidity.session_strategy` | Canonical ST-A2 engine | Legacy mode is used by the adapter; `run_strategy_v2()` exists but is not the current portfolio path.
| `adaptive.strategies.smc_session_strategy` | Thin wrapper around the ST-A2 engine | Emits `smc_session` internally and maps the result to `AdaptiveSMC`.
| `core.signal_router.SignalRouter` | Pre-execution validation | TTL, geometry, and symbol conflict resolution.
| `core.portfolio_manager.PortfolioManager` | Portfolio-level risk and trade caps | Applies confidence, correlation, and daily position limits.

