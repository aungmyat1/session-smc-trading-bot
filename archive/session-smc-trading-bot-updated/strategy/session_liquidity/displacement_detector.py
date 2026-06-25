"""
SA-05 — Displacement Detector.

wilder_atr(candles, period=14) → list[float | None]
detect_displacement(candle, atr, direction, mult=1.2) → DisplacementResult

Displacement (Phase 6 of Strategy A) is the institutional confirmation candle
that must appear within SWEEP_TIMEOUT_BARS bars after a liquidity sweep.

Bullish displacement:
  body > mult × ATR(14)
  close in upper 25% of candle range  (close_position > 0.75)

Bearish displacement:
  body > mult × ATR(14)
  close in lower 25% of candle range  (close_position < 0.25)

Both gates use strict inequality. A candle at exactly the threshold fails.

ATR algorithm — Wilder's method:
  TR[i] = max(high[i]−low[i], |high[i]−close[i−1]|, |low[i]−close[i−1]|)  i ≥ 1
  Seed:      ATR[period]   = mean(TR[1 .. period])     (first `period` TR values)
  Recursive: ATR[i]        = (ATR[i−1] × (period−1) + TR[i]) / period    i > period
  Undefined: ATR[0 .. period−1] = None

The seed uses TR[1..period], not TR[0..period-1]. TR[0] would require a prior
close that is outside the supplied dataset — it is intentionally excluded to
avoid importing phantom data. This means the first valid ATR is at index `period`
(the (period+1)-th bar), matching the TASK_QUEUE "seed at index 14" requirement.
"""

from dataclasses import dataclass


@dataclass
class DisplacementResult:
    """
    Outcome of evaluating one candle for institutional displacement.

    Fields:
        detected        — True when both body and quartile gates pass.
        side            — 'long' | 'short' | None
        body_size       — abs(close − open) in price units
        atr             — ATR value supplied to this evaluation
        close_position  — (close − low) / (high − low); None if body gate fails first
        reason          — descriptor; 'bullish_displacement' | 'bearish_displacement'
                          when detected, rejection detail otherwise
    """
    detected: bool
    side: "str | None"
    body_size: float
    atr: "float | None"
    close_position: "float | None"
    reason: str


# ── ATR ───────────────────────────────────────────────────────────────────────

def wilder_atr(candles: list[dict], period: int = 14) -> "list[float | None]":
    """
    Compute Wilder's ATR for every bar in `candles`.

    Args:
        candles: list of dicts with float-valued 'high', 'low', 'close'.
                 Must be in chronological order.
        period:  smoothing window. Default 14 (standard for M15 Strategy A).

    Returns:
        List of the same length as `candles`.
        Indices 0 .. period−1 → None  (insufficient history)
        Index  period          → seed  (mean of TR[1..period])
        Indices period+1 ..    → recursive Wilder ATR

    Wilder seed note:
        The seed is computed from TR[1..period] (candles[1] through candles[period]).
        TR[0] is intentionally omitted — it would use a "previous close" that does not
        exist in the supplied data. As a result, the first valid ATR is at index `period`
        (not `period − 1`). With the default period=14, ATR[13] is None, ATR[14] is seed.
    """
    n = len(candles)
    atrs: list = [None] * n

    if n <= period:
        return atrs

    # ── True Range for each bar that has a prior bar ──────────────────────────
    trs: list[float] = []
    for i in range(1, n):
        h = candles[i]["high"]
        l = candles[i]["low"]
        pc = candles[i - 1]["close"]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))

    # ── Seed: mean of the first `period` TR values (candles[1..period]) ───────
    seed = sum(trs[:period]) / period
    atrs[period] = seed

    # ── Recursive Wilder smoothing ────────────────────────────────────────────
    for i in range(period + 1, n):
        atrs[i] = (atrs[i - 1] * (period - 1) + trs[i - 1]) / period

    return atrs


# ── Displacement gate ─────────────────────────────────────────────────────────

def detect_displacement(
    candle: dict,
    atr: "float | None",
    direction: str,
    mult: float = 1.2,
) -> DisplacementResult:
    """
    Evaluate a single completed M15 candle for institutional displacement.

    Args:
        candle:    dict with float-coercible keys 'high', 'low', 'open', 'close'.
        atr:       Wilder ATR(14) for this bar index; None if bar is in warm-up period.
        direction: 'long' (after bullish sweep) | 'short' (after bearish sweep).
        mult:      ATR multiplier for body-size gate. Default 1.2 per Strategy A spec.

    Returns:
        DisplacementResult with detected=True only when:
          1. ATR is available (not None, not zero)
          2. body > mult × ATR   (strict inequality)
          3. close_position > 0.75  (long) or < 0.25  (short)   (strict inequality)

    Body gate uses strict >: a candle body exactly equal to the threshold fails.
    Quartile gate uses strict >/>: a close exactly at 0.75 or 0.25 fails.
    """
    # ── 1. Validate candle ───────────────────────────────────────────────────
    try:
        high  = float(candle["high"])
        low   = float(candle["low"])
        open_ = float(candle["open"])
        close = float(candle["close"])
    except (KeyError, TypeError, ValueError):
        return DisplacementResult(
            detected=False, side=None, body_size=0.0,
            atr=atr, close_position=None, reason="invalid_candle",
        )

    # ── 2. ATR availability ──────────────────────────────────────────────────
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

    # ── 3. Zero-range guard ──────────────────────────────────────────────────
    candle_range = high - low
    if candle_range <= 0:
        body_zr = abs(close - open_)
        return DisplacementResult(
            detected=False, side=None, body_size=body_zr,
            atr=atr, close_position=None, reason="zero_range_candle",
        )

    # ── 4. Body gate (strict >) ───────────────────────────────────────────────
    body = abs(close - open_)
    threshold = mult * atr

    if body <= threshold:
        return DisplacementResult(
            detected=False, side=None, body_size=body,
            atr=atr, close_position=None,
            reason=f"body({body:.5f}) ≤ {mult}×ATR({threshold:.5f})",
        )

    # ── 5. Quartile gate (strict inequalities) ────────────────────────────────
    close_pos = (close - low) / candle_range

    if direction == "long":
        if close_pos > 0.75:
            return DisplacementResult(
                detected=True, side="long", body_size=body,
                atr=atr, close_position=close_pos,
                reason="bullish_displacement",
            )
        return DisplacementResult(
            detected=False, side=None, body_size=body,
            atr=atr, close_position=close_pos,
            reason=f"close_pos({close_pos:.2%}) ≤ 75% (bullish quartile)",
        )

    if direction == "short":
        if close_pos < 0.25:
            return DisplacementResult(
                detected=True, side="short", body_size=body,
                atr=atr, close_position=close_pos,
                reason="bearish_displacement",
            )
        return DisplacementResult(
            detected=False, side=None, body_size=body,
            atr=atr, close_position=close_pos,
            reason=f"close_pos({close_pos:.2%}) ≥ 25% (bearish quartile)",
        )

    # ── 6. Unknown direction ──────────────────────────────────────────────────
    return DisplacementResult(
        detected=False, side=None, body_size=body,
        atr=atr, close_position=close_pos,
        reason=f"unknown_direction: {direction!r}",
    )
