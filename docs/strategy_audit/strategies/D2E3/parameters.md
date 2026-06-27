# D2E3 Parameters

## Engine Defaults

| Parameter | Default | Meaning |
| --- | --- | --- |
| `session_start` | `8` | UTC hour inclusive. |
| `session_end` | `16` | UTC hour exclusive. |
| `confirm_bars` | `12` | Maximum bars allowed between sweep and MSS. |
| `entry_wait_bars` | `3` | Maximum bars allowed between MSS and limit fill. |
| `min_stop_pips` | `2.0` | Minimum accepted stop size. |
| `max_stop_pips` | `25.0` | Maximum accepted stop size. |
| `rr` | `2.0` | Fallback RR target. |
| `cooldown_bars` | `3` | Cooldown after a trade closes. |
| `max_hold_bars` | `32` | Maximum hold time in M15 bars. |

## Supporting Constants

- `PIP`: `EURUSD=0.0001`, `GBPUSD=0.0001`
- `SL_BUFFER_PIPS`: `EURUSD=2.0`, `GBPUSD=2.0`
- Rolling MSS pivot lookback: `12` bars

