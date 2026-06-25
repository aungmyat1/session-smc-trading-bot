"""
D2 daily context layer — adds 1D structure above the 4H+1H bias.

Provides:
  aggregate_to_daily()    — build D1 candles from H4 data (no extra download needed)
  build_daily_context()   — PDH, PDL, daily structure, price location
  classify_location()     — 'premium' | 'discount' | 'equilibrium' vs PDH/PDL midpoint

Usage in generate_signal_A():
    from .daily_bias import build_daily_context, classify_location
    ctx = build_daily_context(candles_4h, session_start_time)
    if ctx is not None:
        # gate: daily structure must not conflict with 4H+1H bias
        # gate: session open price must be in the right zone for the trade direction
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional

from .swing_detector import classify_structure

Candle = dict
_UTC = timezone.utc


def _parse_utc(t) -> datetime:
    if isinstance(t, datetime):
        return t if t.tzinfo else t.replace(tzinfo=_UTC)
    return datetime.fromisoformat(str(t).replace("Z", "+00:00"))


def aggregate_to_daily(candles_4h: list[Candle]) -> list[Candle]:
    """
    Build UTC-day OHLCV candles from H4 bars.

    Each calendar date (UTC) becomes one D1 bar. The bar's 'time' field is
    set to YYYY-MM-DDT00:00:00Z.  Bars from Saturdays and empty days are
    included as-is so the caller can filter by date without offset errors.

    Returns bars sorted chronologically.
    """
    days: dict[str, Candle] = {}
    for c in candles_4h:
        date_key = str(c["time"])[:10]  # "YYYY-MM-DD"
        if date_key not in days:
            days[date_key] = {
                "time": date_key + "T00:00:00Z",
                "open": float(c["open"]),
                "high": float(c["high"]),
                "low": float(c["low"]),
                "close": float(c["close"]),
            }
        else:
            b = days[date_key]
            b["high"] = max(b["high"], float(c["high"]))
            b["low"] = min(b["low"], float(c["low"]))
            b["close"] = float(c["close"])
    return sorted(days.values(), key=lambda x: x["time"])


def build_daily_context(
    candles_4h: list[Candle],
    before_dt,
    swing_n: int = 3,
) -> Optional[dict]:
    """
    Build the D2 daily compass for a session starting at before_dt.

    Only fully closed daily bars are used (bars whose date < before_dt.date()).
    Requires at least 2*swing_n+3 daily bars for structure detection.

    Parameters
    ----------
    candles_4h : H4 bars — used to build D1 internally (no extra data needed)
    before_dt  : UTC datetime of the session open bar
    swing_n    : swing confirmation parameter (default 3)

    Returns
    -------
    {
      'pdh'       : float,   # previous day high
      'pdl'       : float,   # previous day low
      'daily_mid' : float,   # midpoint of pdh/pdl range
      'structure' : str,     # 'bullish' | 'bearish' | 'neutral'
    }
    or None if insufficient history.
    """
    before = _parse_utc(before_dt)
    cutoff_date = before.date().isoformat()  # "YYYY-MM-DD" — exclude today

    daily = aggregate_to_daily(candles_4h)
    # Keep only fully closed days (strictly before session date)
    closed = [d for d in daily if d["time"][:10] < cutoff_date]

    if len(closed) < 2:
        return None

    pdh = closed[-1]["high"]
    pdl = closed[-1]["low"]
    daily_mid = (pdh + pdl) / 2.0

    structure = classify_structure(closed, swing_n)

    return {
        "pdh": pdh,
        "pdl": pdl,
        "daily_mid": daily_mid,
        "structure": structure,
    }


def classify_location(price: float, pdh: float, pdl: float) -> str:
    """
    Where is price relative to the previous day's range midpoint?

    'premium'      — above midpoint (price is in the top half of the range)
    'discount'     — below midpoint (price is in the bottom half)
    'equilibrium'  — exactly at midpoint or range is zero
    """
    if pdh <= pdl:
        return "equilibrium"
    mid = (pdh + pdl) / 2.0
    if price > mid:
        return "premium"
    if price < mid:
        return "discount"
    return "equilibrium"
