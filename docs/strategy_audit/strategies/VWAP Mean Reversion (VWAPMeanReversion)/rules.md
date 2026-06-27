# VWAP Mean Reversion Rules

## Entry Rules

- Require at least `min_session_bars` bars in the active session.
- Require a positive VWAP and ATR.
- Long requires a downside sweep, reclaim, and close below VWAP.
- Short requires an upside sweep, fade, and close above VWAP.
- Use VWAP as the profit anchor when it is closer than the raw RR target.

## Invalidation Rules

- No signal if VWAP or ATR cannot be computed.
- No signal if the risk geometry is non-positive.
- No signal if the session does not match London or New York.

## Alias Note

- `VWAPBreakout` is a compatibility shell only.
- The emitted `core.Signal.strategy_name` remains `VWAPMeanReversion`.

