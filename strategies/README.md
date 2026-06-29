# strategies — Strategy Adapter Layer

Date: 2026-06-29
Status: Authoritative
Version: 1.0
Updated: 2026-06-29
Owner: Platform / Quant Research
Authority: Level 6 — Module Documentation
Related: docs/04_Strategy_Specs/, docs/SIGNAL_SPEC.md, docs/svos/CORE_ARCHITECTURE.md

## Purpose

This package provides the adapter layer that connects strategy specifications
to the execution and simulation runtime. Each adapter translates a strategy's
own internal signal representation into the canonical `core.Signal` interface
expected by the execution layer.

The adapter layer enforces a strict boundary: underlying strategy code is never
modified. Adapters are thin translation wrappers only.

## Architecture

All adapters inherit from `core.base_strategy.BaseStrategy` and implement a
single required method:

```
generate_signal(data: dict) -> Optional[core.Signal]
```

The `data` dict carries the market inputs the adapter needs (candle lists,
symbol, optional config). Each adapter documents its own `data` schema in its
module docstring. The adapter calls the underlying strategy module internally,
translates the last raw signal to `core.Signal`, and returns it. If the
underlying strategy module is unavailable (ImportError) or produces no signal,
the adapter returns `None`.

Adapters use graceful import guards (`try/except ImportError`) so the package
loads cleanly even when an upstream strategy module is not installed.

## Package Contents

| File | Purpose |
|---|---|
| `adapters/` | Sub-package of strategy adapters (see below) |
| `shadow_tracker.py` | Records signals from unvalidated strategies without placing orders |

## adapters/ — Strategy Adapters

| Adapter | Class | Strategy | Upstream module | Status |
|---|---|---|---|---|
| `st_a2_adapter.py` | `ST2Adapter` | ST-A2 Session Liquidity Reversal | `strategy.session_liquidity.session_strategy` | DEFERRED_REVALIDATION — do not use for new runs |
| `london_breakout_adapter.py` | `LondonBreakoutAdapter` | London Breakout | `adaptive.strategies.london_breakout_strategy` | Research / unvalidated |
| `ny_momentum_adapter.py` | `NYMomentumAdapter` | NY Momentum | `adaptive.strategies.ny_momentum_strategy` | Research / unvalidated |
| `adaptive_smc_adapter.py` | `AdaptiveSMCAdapter` | Adaptive SMC Session | `adaptive.strategies.smc_session_strategy.SMCSessionStrategy` | Research / unvalidated |
| `smc_ob_fvg_session_adapter.py` | `SMCOrderBlockFVGSessionAdapter` | SMC Order Block + FVG Session | Self-contained using `src.features.fvg` + `src.features.order_blocks` | Intake / SVOS-ready |
| `vwap_adapter.py` | `VWAPMeanReversionAdapter` | VWAP Mean Reversion | Self-contained (no upstream import) | Research / unvalidated |

### Adapter input schemas

**ST2Adapter** (`st_a2_adapter.py`)
- `data["symbol"]`: str
- `data["m15"]`: list[dict] — minimum 50 M15 candles required
- `data["h4"]`: list[dict] — 100 H4 candles recommended
- `data["config"]`: dict — optional; defaults to `DEFAULT_CONFIG` from the upstream module

**LondonBreakoutAdapter** (`london_breakout_adapter.py`)
- `data["symbol"]`: str
- `data["m15"]`: list[dict] — minimum 30 bars required
- `data["spread_pips"]`: float — used for cost-aware signal filtering

**NYMomentumAdapter** (`ny_momentum_adapter.py`)
- `data["symbol"]`: str
- `data["m15"]`: list[dict] — minimum 30 bars required

**AdaptiveSMCAdapter** (`adaptive_smc_adapter.py`)
- `data["symbol"]`: str
- `data["m15"]`: list[dict] — minimum 50 bars required
- `data["h4"]`: list[dict]
- `data["spread_pips"]`: float
- `data["htf_bias"]`: str

**VWAPMeanReversionAdapter** (`vwap_adapter.py`)
- Self-contained; no upstream strategy import.
- Implements session-scoped VWAP fade for London (07:00–09:59 UTC) and New York
  (13:00–15:59 UTC) windows.
- Legacy alias `VWAPBreakoutAdapter` is retained for backwards compatibility.

**SMCOrderBlockFVGSessionAdapter** (`smc_ob_fvg_session_adapter.py`)
- Self-contained; no upstream strategy import.
- Implements London / New York kill-zone filtering, recent BOS detection, order
  block retest logic, FVG confirmation, and ATR-based displacement / stop
  placement for an SVOS intake-ready SMC strategy.

### Pip size table

All adapters that compute pip-based SL/TP distances share the same constant table:

| Symbol | Pip size |
|---|---|
| EURUSD | 0.0001 |
| GBPUSD | 0.0001 |
| USDJPY | 0.01 |
| XAUUSD | 0.1 |

Symbols not in the table fall back to 0.0001.

## shadow_tracker.py — ShadowTracker

`ShadowTracker` records signals from strategies that are not yet execution-validated,
without placing any orders. It operates in `SIGNAL_ONLY` mode.

**Journal path:** `logs/shadow_trades.jsonl` (default; overridable via constructor).

Each record written contains:

| Field | Description |
|---|---|
| `type` | Always `"SHADOW_SIGNAL"` |
| `timestamp` | UTC ISO-8601 at time of tracking |
| `strategy_name` | From the signal |
| `symbol` | From the signal |
| `action` | `BUY` or `SELL` |
| `entry_price`, `stop_loss`, `take_profit` | From the signal |
| `confidence`, `risk_percent`, `session` | From the signal |
| `reason` | Caller-supplied string (default `"shadow_mode"`) |
| `metadata` | From the signal |
| `executed` | Always `false` |

Public methods:

- `track(signal, reason)` — append one record; never raises (logs OSError)
- `read_all()` — returns list of all records from journal
- `summary()` — returns `{"total_shadow_signals": int, "by_strategy": dict}`

## Lifecycle Role

Adapters exist solely to serve the execution and virtual demo layers. They are
only loaded once a strategy has:

1. A valid Approved Strategy Package (Phase 0–5 all PASS)
2. Passed the EXECUTION_VALIDATION stage

**Adapters must NOT be instantiated directly for backtesting or replay.**
The canonical research pipeline uses strategy-specific code in `strategy/` and
`adaptive/`, not the adapter wrappers.

During Phase 5 (Virtual Demo), unvalidated strategies may be run via
`ShadowTracker` to accumulate observable signal history without placing orders.

## Adding a New Strategy Adapter

To add an adapter for a new strategy:

1. Create a file in `adapters/` with a class that:
   - Inherits from `core.base_strategy.BaseStrategy`
   - Implements `name` (property returning a short string identifier)
   - Implements `generate_signal(data: dict) -> Optional[Signal]`
   - Guards the upstream import with `try/except ImportError`
   - Documents the `data` schema in the module docstring
2. Register the new class in `adapters/__init__.py`
3. Ensure the strategy has a current AUDIT stage pass before writing the adapter
4. Do not reference the adapter in execution until EXECUTION_VALIDATION passes
5. Run the strategy via `ShadowTracker` during Phase 5 before enabling live signal routing

## Important: ST-A2 Status

ST-A2 (`st_a2_adapter.py` / `ST2Adapter`) is preserved as legacy research.
ST-A2 is in `DEFERRED_REVALIDATION` state — not current, not approved, not deployable.

Do not use `st_a2_adapter.py` for new qualification runs without re-entering at
INTAKE and passing the full pipeline from Phase 0 with current evidence. See
`CLAUDE.md §6` and `docs/VERDICT_LOG.md` for the deferred status record.
