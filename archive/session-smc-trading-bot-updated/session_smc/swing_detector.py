"""
Swing high / low detector — non-repainting, bar-close only.

CONFIRMATION RULE
-----------------
A swing HIGH at index i is confirmed only when all n bars to the LEFT have a
LOWER high AND all n bars to the RIGHT have a LOWER high.  In a live context
this means index i is callable only after bar i+n has closed.

Practical consequence for callers
----------------------------------
  confirmed = swing_highs(candles[:k+1], n)
  # → indices in range [n, k-n].  candles[k-n] is the most recent confirmable.

All helpers respect this by operating on whatever slice they are given.  The
caller is responsible for slicing to the correct bar horizon before calling.
"""
from __future__ import annotations
from typing import Optional

Candle = dict


# ── Core detectors ────────────────────────────────────────────────────────────

def swing_highs(candles: list[Candle], n: int = 3) -> list[int]:
    """Return indices of confirmed swing highs.  Uses strict inequality."""
    if len(candles) < 2 * n + 1:
        return []
    highs = [c["high"] for c in candles]
    result: list[int] = []
    for i in range(n, len(highs) - n):
        h = highs[i]
        if (all(highs[i - j] < h for j in range(1, n + 1)) and
                all(highs[i + j] < h for j in range(1, n + 1))):
            result.append(i)
    return result


def swing_lows(candles: list[Candle], n: int = 3) -> list[int]:
    """Return indices of confirmed swing lows.  Uses strict inequality."""
    if len(candles) < 2 * n + 1:
        return []
    lows = [c["low"] for c in candles]
    result: list[int] = []
    for i in range(n, len(lows) - n):
        lo = lows[i]
        if (all(lows[i - j] > lo for j in range(1, n + 1)) and
                all(lows[i + j] > lo for j in range(1, n + 1))):
            result.append(i)
    return result


# ── Convenience look-ups ─────────────────────────────────────────────────────

def last_swing_high(
    candles: list[Candle],
    n: int = 3,
    before_idx: Optional[int] = None,
) -> Optional[dict]:
    """
    Most recent confirmed swing high using only candles[0 : before_idx].
    Pass before_idx = sweep_bar_idx to get swings known *before* the sweep.
    Returns {'index': int, 'price': float, 'time': str} or None.
    """
    limit = before_idx if before_idx is not None else len(candles)
    idxs = swing_highs(candles[:limit], n)
    if not idxs:
        return None
    i = idxs[-1]
    return {"index": i, "price": candles[i]["high"], "time": candles[i].get("time")}


def last_swing_low(
    candles: list[Candle],
    n: int = 3,
    before_idx: Optional[int] = None,
) -> Optional[dict]:
    """
    Most recent confirmed swing low using only candles[0 : before_idx].
    Returns {'index': int, 'price': float, 'time': str} or None.
    """
    limit = before_idx if before_idx is not None else len(candles)
    idxs = swing_lows(candles[:limit], n)
    if not idxs:
        return None
    i = idxs[-1]
    return {"index": i, "price": candles[i]["low"], "time": candles[i].get("time")}


# ── Structure classification ─────────────────────────────────────────────────

def classify_structure(
    candles: list[Candle],
    n: int = 3,
    before_idx: Optional[int] = None,
) -> str:
    """
    Classify market structure using the last two confirmed swing pairs.

    Returns
    -------
    'bullish'  — Higher High AND Higher Low
    'bearish'  — Lower Low AND Lower High
    'neutral'  — mixed or insufficient swings
    """
    limit = before_idx if before_idx is not None else len(candles)
    subset = candles[:limit]
    sh_idxs = swing_highs(subset, n)
    sl_idxs = swing_lows(subset, n)

    if len(sh_idxs) < 2 or len(sl_idxs) < 2:
        return "neutral"

    sh = [subset[i]["high"] for i in sh_idxs]
    sl = [subset[i]["low"] for i in sl_idxs]

    hh = sh[-1] > sh[-2]
    hl = sl[-1] > sl[-2]
    ll = sl[-1] < sl[-2]
    lh = sh[-1] < sh[-2]

    if hh and hl:
        return "bullish"
    if ll and lh:
        return "bearish"
    return "neutral"
