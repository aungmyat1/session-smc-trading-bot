"""
Point-of-Interest (POI) detection — Fair Value Gap (FVG).

FVG GEOMETRY
------------
A 3-bar Fair Value Gap is centred on the displacement bar (index d):

  Bullish FVG:
    gap exists when  candles[d+1].low  >  candles[d-1].high
    bottom = candles[d-1].high   (lower edge of the gap)
    top    = candles[d+1].low    (upper edge of the gap)
    price must retrace DOWN into [bottom, top]

  Bearish FVG:
    gap exists when  candles[d+1].high  <  candles[d-1].low
    bottom = candles[d+1].high   (lower edge of the gap)
    top    = candles[d-1].low    (upper edge of the gap)
    price must retrace UP into [bottom, top]

RETEST & INVALIDATION
---------------------
Bullish:
  Retest      → bar.low ≤ top  AND  bar.close ≥ bottom  (touched zone, held)
  Invalidated → bar.close < bottom  (closed through the gap)

Bearish:
  Retest      → bar.high ≥ bottom  AND  bar.close ≤ top
  Invalidated → bar.close > top
"""
from __future__ import annotations
from typing import Optional

Candle = dict


def find_fvg(
    candles: list[Candle],
    displacement_idx: int,
    direction: str,
) -> Optional[dict]:
    """
    Find a Fair Value Gap centred on displacement_idx.
    Requires candles[displacement_idx - 1] and candles[displacement_idx + 1].

    Returns
    -------
    {top, bottom, midpoint, displacement_idx}  or  None
    """
    d = displacement_idx
    if d < 1 or d + 1 >= len(candles):
        return None

    prev_c = candles[d - 1]
    next_c = candles[d + 1]

    if direction == "bullish":
        bottom = prev_c["high"]
        top = next_c["low"]
        if top > bottom:
            return {
                "top": top,
                "bottom": bottom,
                "midpoint": (top + bottom) / 2.0,
                "displacement_idx": d,
            }

    else:  # bearish
        top = prev_c["low"]
        bottom = next_c["high"]
        if top > bottom:
            return {
                "top": top,
                "bottom": bottom,
                "midpoint": (top + bottom) / 2.0,
                "displacement_idx": d,
            }

    return None


def check_fvg_retest(
    candles: list[Candle],
    fvg: dict,
    direction: str,
    from_idx: int,
) -> Optional[int]:
    """
    Scan candles[from_idx:] for the first bar that retests the FVG.

    Returns the index of the retest bar, or None if:
      • The FVG is invalidated (price closed through the gap) before a retest, or
      • No retest occurs before the end of the slice.

    The caller should pass only bars within the session window to enforce
    the session-end exit rule.
    """
    top = fvg["top"]
    bottom = fvg["bottom"]

    for i in range(from_idx, len(candles)):
        c = candles[i]

        if direction == "bullish":
            if c["low"] <= top:          # price entered the FVG zone from above
                if c["close"] < bottom:  # closed through → invalidated
                    return None
                return i                  # held above bottom → valid retest
            # Price still above zone, keep watching

        else:  # bearish
            if c["high"] >= bottom:      # price entered the FVG zone from below
                if c["close"] > top:     # closed through → invalidated
                    return None
                return i                  # held below top → valid retest
            # Price still below zone, keep watching

    return None
