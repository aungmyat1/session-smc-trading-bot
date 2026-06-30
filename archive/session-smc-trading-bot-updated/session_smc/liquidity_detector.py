"""
Session range construction and liquidity sweep detection.

All functions operate on list[dict] candles (time, open, high, low, close).
The pip size (0.0001) is hard-coded for EURUSD / GBPUSD.  If additional pairs
with different pip sizes are added, pass pip_size as a parameter.
"""

from __future__ import annotations
from typing import Optional

from .structure_detector import atr as compute_atr

Candle = dict
PIP: float = 0.0001  # 1 pip for 5-digit EURUSD / GBPUSD


# ── Session range ─────────────────────────────────────────────────────────────


def build_session_range(
    candles: list[Candle],
    range_bars: int = 8,
    min_range_pips: float = 10.0,
) -> Optional[dict]:
    """
    Build session H/L from the first `range_bars` candles (default 8 = 2 H at 15 M).

    Returns None if fewer than `range_bars` candles are available or the range
    is too narrow (< min_range_pips).

    Returns
    -------
    {high, low, midpoint, range_pips}  or  None
    """
    bars = candles[:range_bars]
    if len(bars) < range_bars:
        return None

    high = max(c["high"] for c in bars)
    low = min(c["low"] for c in bars)
    range_pips = (high - low) / PIP

    if range_pips < min_range_pips:
        return None

    return {
        "high": high,
        "low": low,
        "midpoint": (high + low) / 2.0,
        "range_pips": range_pips,
    }


# ── Session classification ────────────────────────────────────────────────────


def classify_session(
    candles: list[Candle],
    session_range: dict,
    atr_period: int = 14,
) -> str:
    """
    Classify the session volatility character.

    ratio = session_range / ATR(14)
    < 0.5  → 'RANGE'
    > 0.7  → 'TREND'
    else   → 'MIXED'
    """
    atr_vals = compute_atr(candles, atr_period)
    valid = [v for v in atr_vals if v == v]  # exclude NaN
    if not valid:
        return "MIXED"
    cur_atr = valid[-1]
    if cur_atr <= 0:
        return "MIXED"
    ratio = (session_range["high"] - session_range["low"]) / cur_atr
    if ratio < 0.5:
        return "RANGE"
    if ratio > 0.7:
        return "TREND"
    return "MIXED"


# ── Sweep detection ──────────────────────────────────────────────────────────


def detect_sweep(
    candles: list[Candle],
    session_range: dict,
    direction: str,
    from_idx: int,
) -> Optional[dict]:
    """
    Starting from `from_idx`, find the first bar where price sweeps the
    session liquidity level and closes back inside the session range.

    Parameters
    ----------
    direction  : 'bullish' → sweep of session LOW (sell-side liquidity grabbed)
                 'bearish' → sweep of session HIGH (buy-side liquidity grabbed)
    from_idx   : first bar to inspect (usually = range_bars, i.e. after range built)

    Returns
    -------
    {index, sweep_price, wick_extreme, direction}  or  None
    """
    s_high = session_range["high"]
    s_low = session_range["low"]

    for i in range(from_idx, len(candles)):
        c = candles[i]
        if direction == "bullish":
            # Wick below session low, close back above it
            if c["low"] < s_low and c["close"] > s_low:
                return {
                    "index": i,
                    "sweep_price": s_low,
                    "wick_extreme": c["low"],
                    "direction": "bullish",
                }
        else:
            # Wick above session high, close back below it
            if c["high"] > s_high and c["close"] < s_high:
                return {
                    "index": i,
                    "sweep_price": s_high,
                    "wick_extreme": c["high"],
                    "direction": "bearish",
                }
    return None
