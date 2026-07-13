"""
SMC-LSS_v0 — Structure Break (CHoCH) Detection + Inducement Logic.

detect_choch(candles, index, ...) -> StructureBreakEvent | None
apply_inducement(event, sweep_indices, choch_index, ...) -> StructureBreakEvent

Per config/strategies/SMC-LSS_v0.yaml `components.structure`:
    structure_lookback: 10

Spec (as given):
    Bullish CHoCH:  lower low forms / previous lower high breaks / close
                     above lower high
    Bearish CHoCH:  higher high forms / previous higher low breaks / close
                     below previous lower low

ASSUMPTION (documented per task instructions — see
docs/audit/SMC_LSS_V0_BACKTEST_REPORT.md "Assumptions"): the bearish
clause as literally given ("close below previous lower low") does not
mirror the bullish clause and does not correspond to a standard CHoCH
definition — a genuine bearish CHoCH is a break of the most recent HIGHER
LOW during an uptrend, not a break of an unrelated "lower low". This is
treated as a copy/paste inconsistency in the source spec and implemented
symmetrically with the bullish rule: bearish CHoCH requires closing below
the previous HIGHER LOW. This keeps both directions objective, testable,
and mechanically symmetric, and is called out explicitly rather than
silently "fixed" without a trace.

Two non-overlapping lookback windows are compared, both strictly before
the evaluated candle at `index` (no lookahead):
    prior_window  = candles[index - 2*lookback : index - lookback]
    recent_window = candles[index - lookback     : index]

    Bullish: min(low, recent_window) < min(low, prior_window)   ("lower low forms")
             AND candles[index].close > max(high, recent_window) ("previous lower
             high breaks" + "close above lower high" — the recent window's high
             plays the role of the lower high formed during the down-leg)

    Bearish: max(high, recent_window) > max(high, prior_window) ("higher high forms")
             AND candles[index].close < min(low, recent_window)  (close below the
             previous higher low, per the symmetry assumption above)
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class StructureBreakEvent:
    timestamp: object
    symbol: str
    direction: str              # 'long' | 'short'
    broken_level: float         # the "lower high" / "higher low" level broken
    confirmation_close: float
    inducement: bool = False
    inducement_sweep_index: "int | None" = None


def _window_low(candles: list[dict], start: int, end: int) -> "float | None":
    window = candles[max(start, 0):end]
    if not window:
        return None
    return min(c["low"] for c in window)


def _window_high(candles: list[dict], start: int, end: int) -> "float | None":
    window = candles[max(start, 0):end]
    if not window:
        return None
    return max(c["high"] for c in window)


def detect_choch(
    candles: list[dict],
    index: int,
    *,
    symbol: str,
    structure_lookback: int = 10,
) -> "StructureBreakEvent | None":
    """Evaluate `candles[index]`'s close for a Change of Character against
    the two structure_lookback-bar windows strictly before it."""
    if index < 0 or index >= len(candles):
        return None
    if index < 2 * structure_lookback:
        return None

    prior_start = index - 2 * structure_lookback
    prior_end = index - structure_lookback
    recent_start = index - structure_lookback
    recent_end = index

    close = float(candles[index]["close"])

    recent_low = _window_low(candles, recent_start, recent_end)
    prior_low = _window_low(candles, prior_start, prior_end)
    recent_high = _window_high(candles, recent_start, recent_end)
    prior_high = _window_high(candles, prior_start, prior_end)

    if recent_low is not None and prior_low is not None and recent_low < prior_low:
        if recent_high is not None and close > recent_high:
            return StructureBreakEvent(
                timestamp=candles[index].get("timestamp"),
                symbol=symbol,
                direction="long",
                broken_level=recent_high,
                confirmation_close=close,
            )

    if recent_high is not None and prior_high is not None and recent_high > prior_high:
        if recent_low is not None and close < recent_low:
            return StructureBreakEvent(
                timestamp=candles[index].get("timestamp"),
                symbol=symbol,
                direction="short",
                broken_level=recent_low,
                confirmation_close=close,
            )

    return None


def apply_inducement(
    event: StructureBreakEvent,
    sweep_indices: list[int],
    choch_index: int,
    *,
    inducement_window: int = 3,
) -> StructureBreakEvent:
    """
    Return a copy of `event` annotated with inducement status.

    Inducement = a liquidity sweep occurred within the `inducement_window`
    candles strictly before CHoCH confirmation (candles at index
    choch_index - inducement_window .. choch_index - 1).
    """
    qualifying = [
        i for i in sweep_indices
        if choch_index - inducement_window <= i < choch_index
    ]
    inducement_index = max(qualifying) if qualifying else None
    return StructureBreakEvent(
        timestamp=event.timestamp,
        symbol=event.symbol,
        direction=event.direction,
        broken_level=event.broken_level,
        confirmation_close=event.confirmation_close,
        inducement=inducement_index is not None,
        inducement_sweep_index=inducement_index,
    )
