"""
HTF bias, ATR, CHoCH, BOS, and displacement detection.

All functions operate on list[dict] candles and are bar-close safe:
no index beyond len(candles)-1 is read.
"""

from __future__ import annotations

from typing import Optional

from .swing_detector import classify_structure

Candle = dict


# ── Higher-timeframe bias ─────────────────────────────────────────────────────


def htf_bias(
    candles_4h: list[Candle],
    candles_1h: list[Candle],
    swing_n: int = 3,
) -> str:
    """
    Combine 4H structure (primary) with 1H structure (filter).

    Rules
    -----
    4H bullish AND 1H not bearish  → 'bullish'
    4H bearish AND 1H not bullish  → 'bearish'
    All other combinations         → 'neutral'
    """
    b4 = classify_structure(candles_4h, swing_n)
    b1 = classify_structure(candles_1h, swing_n)
    if b4 == "bullish" and b1 != "bearish":
        return "bullish"
    if b4 == "bearish" and b1 != "bullish":
        return "bearish"
    return "neutral"


# ── ATR (Wilder's) ────────────────────────────────────────────────────────────


def atr(candles: list[Candle], period: int = 14) -> list[float]:
    """
    Wilder's ATR aligned to candles (one value per bar).

    Index 0 has no prior close so its TR = high - low.
    The first meaningful ATR value appears at index `period`.
    All earlier values are NaN.
    """
    n = len(candles)
    nan = float("nan")
    if n < 2:
        return [nan] * n

    # True range
    tr: list[float] = [candles[0]["high"] - candles[0]["low"]]
    for i in range(1, n):
        h = candles[i]["high"]
        lo = candles[i]["low"]
        pc = candles[i - 1]["close"]
        tr.append(max(h - lo, abs(h - pc), abs(lo - pc)))

    result = [nan] * n
    if n <= period:
        return result

    # Seed: simple mean of TR[1..period]
    seed = sum(tr[1 : period + 1]) / period
    result[period] = seed
    for i in range(period + 1, n):
        result[i] = (result[i - 1] * (period - 1) + tr[i]) / period

    return result


# ── CHoCH ────────────────────────────────────────────────────────────────────


def detect_choch(
    candles_15m: list[Candle],
    sweep_idx: int,
    direction: str,
    lookback: int = 8,
) -> Optional[dict]:
    """
    Change of Character — first 15M bar after sweep_idx whose close breaks the
    reference level computed from the `lookback` bars immediately before the sweep.

    Parameters
    ----------
    sweep_idx  : local index of the sweep bar in candles_15m
    direction  : 'bullish' (long setup) | 'bearish' (short setup)
    lookback   : bars before sweep used to build the reference level

    Returns
    -------
    {'index': int, 'reference': float} or None
    """
    win_start = max(0, sweep_idx - lookback)
    window = candles_15m[win_start:sweep_idx]
    if not window:
        return None

    if direction == "bullish":
        reference = max(c["high"] for c in window)
        for i in range(sweep_idx + 1, len(candles_15m)):
            if candles_15m[i]["close"] > reference:
                return {"index": i, "reference": reference}
    else:
        reference = min(c["low"] for c in window)
        for i in range(sweep_idx + 1, len(candles_15m)):
            if candles_15m[i]["close"] < reference:
                return {"index": i, "reference": reference}

    return None


# ── BOS ───────────────────────────────────────────────────────────────────────


def detect_bos(
    candles_15m: list[Candle],
    after_idx: int,
    direction: str,
    swing_level: Optional[float],
) -> Optional[dict]:
    """
    Break of Structure — first 15M bar after after_idx whose close breaks
    swing_level in the trade direction.

    swing_level should be the most recent confirmed swing high (bullish) or
    swing low (bearish) from before the sweep event.  Returns None if
    swing_level is None (insufficient history).

    Returns
    -------
    {'index': int, 'level': float} or None
    """
    if swing_level is None:
        return None

    if direction == "bullish":
        for i in range(after_idx + 1, len(candles_15m)):
            if candles_15m[i]["close"] > swing_level:
                return {"index": i, "level": swing_level}
    else:
        for i in range(after_idx + 1, len(candles_15m)):
            if candles_15m[i]["close"] < swing_level:
                return {"index": i, "level": swing_level}

    return None


# ── Displacement ──────────────────────────────────────────────────────────────


def detect_displacement(
    candles_15m: list[Candle],
    start_idx: int,
    end_idx: int,
    direction: str,
    atr_values: list[float],
    atr_mult: float = 1.5,
) -> Optional[dict]:
    """
    First displacement candle in candles_15m[start_idx : end_idx + 1].

    A displacement candle satisfies:
      • range (high − low) ≥ atr_mult × ATR(14) at that index
      • body in the correct direction (bullish close > open / bearish open > close)

    Returns
    -------
    {'index': int, 'high': float, 'low': float, 'open': float, 'close': float}
    or None
    """
    nan = float("nan")
    for i in range(start_idx, min(end_idx + 1, len(candles_15m))):
        atr_val = atr_values[i] if i < len(atr_values) else nan
        if atr_val != atr_val:  # NaN
            continue
        c = candles_15m[i]
        if (c["high"] - c["low"]) < atr_mult * atr_val:
            continue
        if direction == "bullish" and c["close"] > c["open"]:
            return {
                "index": i,
                "high": c["high"],
                "low": c["low"],
                "open": c["open"],
                "close": c["close"],
            }
        if direction == "bearish" and c["close"] < c["open"]:
            return {
                "index": i,
                "high": c["high"],
                "low": c["low"],
                "open": c["open"],
                "close": c["close"],
            }
    return None
