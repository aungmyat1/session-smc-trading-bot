"""
SA-04 — Liquidity Sweep Detector.

detect_sweep(candle, asian_high, asian_low, bias) → SweepResult

A liquidity sweep is confirmed when a candle's wick pierces an Asian session
extreme (strict inequality) and the candle closes back inside the range, in
the direction of the prevailing 4H bias.

  Bullish: low < asian_low AND close > asian_low AND bias == "bullish"
  Bearish: high > asian_high AND close < asian_high AND bias == "bearish"

Strict inequality is enforced on both the breach and the close-back:
  - low == asian_low   → no breach (no_breach)
  - close == asian_low → did not close back (close_outside_range)

This module is intentionally scope-limited to a single candle evaluation.
No displacement, no entry, no session gating — those are in downstream modules.
"""

from dataclasses import dataclass


@dataclass
class SweepResult:
    """
    Outcome of evaluating one candle against the Asian session range.

    Fields:
        detected    — True only when all three conditions pass.
        side        — 'long' | 'short' | None
        sweep_price — candle.low (bullish) or candle.high (bearish) that
                      pierced the level; None when detected is False.
        reason      — 'bullish_sweep' | 'bearish_sweep' when detected;
                      'no_breach' | 'close_outside_range' | 'bias_mismatch' |
                      'invalid_candle' when not detected.
    """
    detected: bool
    side: "str | None"
    sweep_price: "float | None"
    reason: str


def detect_sweep(
    candle: dict,
    asian_high: float,
    asian_low: float,
    bias: str,
) -> SweepResult:
    """
    Evaluate a single completed M15 candle for a liquidity sweep.

    Args:
        candle:     dict with float-coercible keys 'high', 'low', 'close'.
        asian_high: Asian session high (from AsianRange.high).
        asian_low:  Asian session low  (from AsianRange.low).
        bias:       4H structural bias from htf_bias() —
                    'bullish' | 'bearish' | 'neutral'.

    Returns:
        SweepResult with detected=True iff:
          1. bias matches the sweep direction
          2. price strictly breaches the Asian level (wick, not body required)
          3. candle closes back inside the range (reversal candle)
    """
    # ── 1. Validate candle ───────────────────────────────────────────────────
    try:
        high = float(candle["high"])
        low = float(candle["low"])
        close = float(candle["close"])
    except (KeyError, TypeError, ValueError):
        return SweepResult(
            detected=False, side=None, sweep_price=None, reason="invalid_candle"
        )

    # ── 2. Check strict price breach ─────────────────────────────────────────
    # Touch only (low == asian_low or high == asian_high) is NOT a breach.
    bullish_breach = low < asian_low    # wick pierced below Asian low
    bearish_breach = high > asian_high  # wick pierced above Asian high

    if not bullish_breach and not bearish_breach:
        return SweepResult(
            detected=False, side=None, sweep_price=None, reason="no_breach"
        )

    # ── 3. Match breach direction to bias then check close ───────────────────
    if bias == "bullish":
        if not bullish_breach:
            # High breach exists but bias wants longs — directional mismatch
            return SweepResult(
                detected=False, side=None, sweep_price=None, reason="bias_mismatch"
            )
        if close <= asian_low:
            # Closed below or at the swept level — no reversal, still in loss zone
            return SweepResult(
                detected=False, side=None, sweep_price=None, reason="close_outside_range"
            )
        return SweepResult(
            detected=True, side="long", sweep_price=low, reason="bullish_sweep"
        )

    if bias == "bearish":
        if not bearish_breach:
            # Low breach exists but bias wants shorts — directional mismatch
            return SweepResult(
                detected=False, side=None, sweep_price=None, reason="bias_mismatch"
            )
        if close >= asian_high:
            # Closed above or at the swept level — no reversal
            return SweepResult(
                detected=False, side=None, sweep_price=None, reason="close_outside_range"
            )
        return SweepResult(
            detected=True, side="short", sweep_price=high, reason="bearish_sweep"
        )

    # ── 4. Neutral or unrecognised bias ──────────────────────────────────────
    # Cannot determine direction without a committed bias.
    return SweepResult(
        detected=False, side=None, sweep_price=None, reason="bias_mismatch"
    )
