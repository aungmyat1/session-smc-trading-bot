# VWAP Mean Reversion Parameters

## Source Defaults

| Parameter | Default | Meaning |
| --- | --- | --- |
| `_SESSION_HOURS.london` | `07:00-09:59 UTC` | London session window used by the adapter. |
| `_SESSION_HOURS.new_york` | `13:00-15:59 UTC` | New York session window used by the adapter. |
| `_MIN_BARS` | `12` | Minimum bars required before evaluation. |
| `_MIN_SESSION_BARS` | `8` | Minimum bars in a session before the signal logic runs. |
| `_SWEEP_BUFFER_MULT` | `0.35` | Sweep buffer multiplier. |
| `_EXTREME_ATR_MULT` | `1.0` | Distance from VWAP required to consider the move extended. |
| `_RECLAIM_ATR_MULT` | `0.6` | Minimum reclaim strength after the sweep. |
| `_TP_RR` | `1.8` | Default reward/risk target. |

## Symbol Overrides

The adapter allows symbol-specific overrides through `config["parameters"]` for:

- `EURUSD`
- `GBPUSD`
- `XAUUSD`

The portfolio config currently sets different multiplier values per symbol.

