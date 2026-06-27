# Governance And Risk

## Lifecycle Governance

The strategy catalog in `config/strategy_catalog.yaml` uses the lifecycle order:

`draft -> research -> replay -> backtest -> walk_forward -> shadow -> demo -> live -> retired`

The registry treats `approved: true` as a prerequisite for deployment gating. A strategy must also have a lifecycle stage at or above the requested target stage.

## Current Risk Controls

`config/strategy_portfolio.yaml` currently enforces:

- `max_trades_per_day: 4`
- `max_open_positions: 3`
- `daily_loss_limit_pct: 2.0`
- `weekly_loss_limit_pct: 5.0`
- `monthly_loss_limit_pct: 8.0`
- `min_confidence: 0.65`

`core/portfolio_manager.py` has broader defaults, but the portfolio config above is the active runtime override when the YAML is available.

## Layered Safety Checks

1. `SignalRouter` rejects stale, malformed, or conflicting signals.
1. `CircuitBreaker` enforces per-strategy rate limits and consecutive-loss cooldowns.
1. `PortfolioManager` enforces enabled strategy filters, minimum confidence, correlation limits, and global trade caps.
1. Execution-layer logic is separated from signal generation.

## Risk Tier Notes

`core/portfolio_manager.py` maps strategies to tiers:

- `tier1`: `ST-A2`
- `tier2`: `LondonBreakout`, `NYMomentum`
- `tier3`: `AdaptiveSMC`, `VWAPMeanReversion`, `VWAPBreakout`

Important audit note: the adapters currently set `risk_percent` on the emitted `core.Signal` objects independently of the portfolio tier table. That means the signal payload and the portfolio risk table should be checked together before any live deployment decision.

