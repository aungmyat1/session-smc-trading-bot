# System Rules

## Signal Validation

- Reject signals with missing `symbol`, invalid `action`, or non-positive `entry_price`.
- Reject signals when timestamp parsing fails or when the signal is older than `ttl_seconds`.
- For `BUY`, require `stop_loss < entry_price < take_profit`.
- For `SELL`, require `take_profit < entry_price < stop_loss`.
- `CLOSE` signals bypass geometry validation.

## Conflict Handling

- Conflicting `BUY` and `SELL` signals on the same symbol are rejected together.
- Same-direction signals on the same symbol are reduced to the highest-confidence signal.
- Portfolio-level correlation groups suppress duplicate directional exposure inside the same correlated basket.

## Trade Caps And Cooldowns

- Portfolio config currently caps total open positions at 3.
- Portfolio config currently caps total new trades at 4 per day.
- Circuit breaker defaults add per-strategy rate limits and cooldowns after repeated losses.

## Strategy-Specific Rule Families

- ST-A2 requires: HTF bias, Asian range, liquidity sweep, displacement within timeout, and minimum stop distance.
- London Breakout requires: valid Asian range, London-session breakout close, and retest.
- NY Momentum requires: London high/low sweep, close beyond the swept level, and retest.
- VWAP Mean Reversion requires: enough session bars, extension away from VWAP, sweep of local extremes, and reclaim back toward fair value.
- D2E3 requires: PDH/PDL sweep, MSS confirmation, and a valid entry window before the setup expires.

