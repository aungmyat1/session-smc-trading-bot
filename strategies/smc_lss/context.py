"""
SMC-LSS_v0 — HTF Context Builder.

build_session_context(...) -> SessionContext | None

Produces the daily/H1 context each entry model reacts against:
    daily_bias, previous_day_high, previous_day_low, daily_open,
    daily_gap, H1_POI

No-lookahead discipline: callers must pass only fully CLOSED daily candles
in `prior_daily_candles` and fully CLOSED H1 candles in `prior_h1_candles`.
The in-progress day's open (`current_daily_open`) is accepted separately
as a scalar because a bar's open is known the instant it starts — its
high/low/close are not, and are deliberately never accessed here.
"""

from __future__ import annotations

from dataclasses import dataclass

from .displacement import detect_displacement, wilder_atr


@dataclass
class SessionContext:
    daily_bias: str              # 'bullish' | 'bearish' | 'neutral'
    previous_day_high: float
    previous_day_low: float
    daily_open: float
    daily_gap: float             # daily_open - previous_day_close
    H1_POI: "float | None"       # midpoint of most recent qualifying H1 displacement candle


def _daily_bias(previous_day: dict) -> str:
    open_ = float(previous_day["open"])
    close = float(previous_day["close"])
    if close > open_:
        return "bullish"
    if close < open_:
        return "bearish"
    return "neutral"


def _h1_poi(
    prior_h1_candles: list[dict],
    bias: str,
    *,
    atr_period: int,
    displacement_body_atr: float,
) -> "float | None":
    """Most recent H1 displacement candle (in the bias direction) among the
    supplied closed H1 candles; POI = midpoint of that candle's body."""
    if bias not in ("bullish", "bearish") or len(prior_h1_candles) <= atr_period:
        return None

    direction = "long" if bias == "bullish" else "short"
    atrs = wilder_atr(prior_h1_candles, period=atr_period)

    for i in range(len(prior_h1_candles) - 1, atr_period - 1, -1):
        result = detect_displacement(
            prior_h1_candles[i], atrs[i], direction,
            body_atr_mult=displacement_body_atr,
        )
        if result.detected:
            candle = prior_h1_candles[i]
            return (float(candle["open"]) + float(candle["close"])) / 2.0
    return None


def build_session_context(
    prior_daily_candles: list[dict],
    current_daily_open: float,
    prior_h1_candles: list[dict],
    *,
    atr_period: int = 14,
    displacement_body_atr: float = 1.5,
) -> "SessionContext | None":
    """Build the HTF context available at the start of the current day.

    Returns None if there is no prior daily candle (insufficient history —
    cannot determine bias, previous day range, or gap)."""
    if not prior_daily_candles:
        return None

    previous_day = prior_daily_candles[-1]
    bias = _daily_bias(previous_day)
    previous_day_high = float(previous_day["high"])
    previous_day_low = float(previous_day["low"])
    previous_day_close = float(previous_day["close"])
    daily_gap = current_daily_open - previous_day_close

    h1_poi = _h1_poi(
        prior_h1_candles, bias,
        atr_period=atr_period,
        displacement_body_atr=displacement_body_atr,
    )

    return SessionContext(
        daily_bias=bias,
        previous_day_high=previous_day_high,
        previous_day_low=previous_day_low,
        daily_open=current_daily_open,
        daily_gap=daily_gap,
        H1_POI=h1_poi,
    )
