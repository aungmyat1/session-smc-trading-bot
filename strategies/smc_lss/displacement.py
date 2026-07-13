"""
SMC-LSS_v0 — Displacement Engine.

wilder_atr(candles, period=14) -> list[float | None]
detect_displacement(candle, atr, direction, ...) -> DisplacementResult

An institutional displacement candle confirms a liquidity sweep is being
defended, not just wicked through. Per config/strategies/SMC-LSS_v0.yaml
`components.displacement`:

    body >= 1.5 * ATR(14)
    AND (bull candle closes in top 25% of its range
         OR bear candle closes in bottom 25% of its range)

Both gates use non-strict inequality (>=, <=) — a candle exactly at the
threshold PASSES. This differs deliberately from
strategy/session_liquidity/displacement_detector.py (which uses strict >
at mult=1.2); SMC-LSS_v0's spec text uses ">=" explicitly, so the two
strategies' edge behavior is intentionally different and this is not a bug.

Self-contained: does not import strategy/session_liquidity or any other
strategy package, to keep SMC-LSS_v0 fully isolated (CLAUDE.md "keep all
changes isolated under SMC-LSS_v0").
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DisplacementResult:
    """
    Outcome of evaluating one candle for institutional displacement.

    Fields:
        detected       — True when both the body gate and quartile gate pass.
        side           — 'long' | 'short' | None
        body_size      — abs(close - open), price units
        atr            — ATR value supplied to this evaluation
        close_position — (close - low) / (high - low); None if a prior gate failed
        reason         — 'bullish_displacement' | 'bearish_displacement' when
                          detected, rejection detail otherwise
    """

    detected: bool
    side: "str | None"
    body_size: float
    atr: "float | None"
    close_position: "float | None"
    reason: str


def wilder_atr(candles: list[dict], period: int = 14) -> "list[float | None]":
    """
    Wilder's ATR for every bar in `candles` (chronological order required).

    Indices 0..period-1  -> None (insufficient history)
    Index   period       -> seed = mean(TR[1..period])
    Indices period+1..   -> recursive Wilder smoothing

    TR[0] is intentionally excluded from the seed (it would require a
    close before the supplied dataset begins) — first valid ATR is at
    index `period`, not `period - 1`.
    """
    n = len(candles)
    atrs: "list[float | None]" = [None] * n
    if n <= period:
        return atrs

    trs: list[float] = []
    for i in range(1, n):
        h = candles[i]["high"]
        lo = candles[i]["low"]
        pc = candles[i - 1]["close"]
        trs.append(max(h - lo, abs(h - pc), abs(lo - pc)))

    seed = sum(trs[:period]) / period
    atrs[period] = seed

    for i in range(period + 1, n):
        atrs[i] = (atrs[i - 1] * (period - 1) + trs[i - 1]) / period

    return atrs


def detect_displacement(
    candle: dict,
    atr: "float | None",
    direction: str,
    *,
    body_atr_mult: float = 1.5,
    close_quartile: float = 0.25,
) -> DisplacementResult:
    """
    Evaluate a single completed candle for institutional displacement.

    Args:
        candle:         dict with float-coercible 'open','high','low','close'.
        atr:            ATR(14) for this bar; None if in warm-up period.
        direction:      'long' (after bullish sweep) | 'short' (after bearish sweep).
        body_atr_mult:  ATR multiplier for the body-size gate. Default 1.5.
        close_quartile: quartile width for the close-position gate. Default 0.25.
    """
    try:
        high = float(candle["high"])
        low = float(candle["low"])
        open_ = float(candle["open"])
        close = float(candle["close"])
    except (KeyError, TypeError, ValueError):
        return DisplacementResult(
            detected=False, side=None, body_size=0.0,
            atr=atr, close_position=None, reason="invalid_candle",
        )

    if atr is None:
        return DisplacementResult(
            detected=False, side=None, body_size=abs(close - open_),
            atr=None, close_position=None, reason="atr_unavailable",
        )
    if atr <= 0:
        return DisplacementResult(
            detected=False, side=None, body_size=abs(close - open_),
            atr=atr, close_position=None, reason="atr_zero",
        )

    candle_range = high - low
    if candle_range <= 0:
        return DisplacementResult(
            detected=False, side=None, body_size=abs(close - open_),
            atr=atr, close_position=None, reason="zero_range_candle",
        )

    body = abs(close - open_)
    threshold = body_atr_mult * atr
    if body < threshold:
        return DisplacementResult(
            detected=False, side=None, body_size=body,
            atr=atr, close_position=None,
            reason=f"body({body:.5f}) < {body_atr_mult}xATR({threshold:.5f})",
        )

    close_pos = (close - low) / candle_range

    if direction == "long":
        if close_pos >= 1.0 - close_quartile:
            return DisplacementResult(
                detected=True, side="long", body_size=body,
                atr=atr, close_position=close_pos, reason="bullish_displacement",
            )
        return DisplacementResult(
            detected=False, side=None, body_size=body,
            atr=atr, close_position=close_pos,
            reason=f"close_pos({close_pos:.2%}) < {1.0 - close_quartile:.0%} (bullish quartile)",
        )

    if direction == "short":
        if close_pos <= close_quartile:
            return DisplacementResult(
                detected=True, side="short", body_size=body,
                atr=atr, close_position=close_pos, reason="bearish_displacement",
            )
        return DisplacementResult(
            detected=False, side=None, body_size=body,
            atr=atr, close_position=close_pos,
            reason=f"close_pos({close_pos:.2%}) > {close_quartile:.0%} (bearish quartile)",
        )

    return DisplacementResult(
        detected=False, side=None, body_size=body,
        atr=atr, close_position=close_pos,
        reason=f"unknown_direction: {direction!r}",
    )
