"""
Adaptive Session Engine v1 — Signal Scoring Engine.

Scores incoming strategy signals against a set of criteria.
A signal must score >= MIN_SCORE to be approved for routing.

Public API:
    score_signal(signal, context) -> dict
"""

from __future__ import annotations

from adaptive.strategies import AdaptiveSignal

MIN_SCORE = 7

# Pair-specific spread thresholds (pips)
_MAX_SPREAD: dict[str, float] = {
    "EURUSD": 1.5,
    "GBPUSD": 2.0,
    "USDJPY": 2.0,
}

# Volatility: ATR% ceiling — too volatile is also penalised
_MAX_ATR_PCT = 0.008  # 0.8% of price
_MIN_ATR_PCT = 0.001  # 0.1% of price

# Active session windows (UTC hour, inclusive)
_SESSION_WINDOWS: dict[str, tuple[int, int]] = {
    "london": (6, 9),
    "new_york": (11, 15),
}


def _htf_bias_aligned(signal: AdaptiveSignal, context: dict) -> bool:
    """True if context['htf_bias'] matches signal direction."""
    bias = context.get("htf_bias", "").upper()
    if not bias or bias == "NEUTRAL":
        return False
    return (signal.direction == "LONG" and bias == "BULLISH") or (
        signal.direction == "SHORT" and bias == "BEARISH"
    )


def _has_liquidity_event(signal: AdaptiveSignal) -> bool:
    return bool(signal.metadata.get("liquidity_swept", False))


def _has_structure_confirmation(signal: AdaptiveSignal) -> bool:
    return bool(signal.metadata.get("structure_confirmed", False))


def _in_active_session(signal: AdaptiveSignal, utc_hour: int) -> bool:
    window = _SESSION_WINDOWS.get(signal.session)
    if window is None:
        return False
    return window[0] <= utc_hour <= window[1]


def _spread_acceptable(signal: AdaptiveSignal, spread_pips: float) -> bool:
    threshold = _MAX_SPREAD.get(signal.pair, 2.0)
    return spread_pips <= threshold


def _volatility_acceptable(atr_pct: float) -> bool:
    return _MIN_ATR_PCT <= atr_pct <= _MAX_ATR_PCT


def _news_clear(context: dict) -> bool:
    """Default True in demo mode — override by setting context['news_event']=True."""
    return not context.get("news_event", False)


# ── Public API ────────────────────────────────────────────────────────────────


def score_signal(signal: AdaptiveSignal, context: dict) -> dict:
    """
    Score a strategy signal against objective criteria.

    Args:
        signal:  AdaptiveSignal from any strategy module.
        context: Runtime context dict. Expected keys:
            htf_bias:    "BULLISH" | "BEARISH" | "NEUTRAL"
            utc_hour:    int (0-23), current UTC hour
            spread_pips: float, current spread in pips
            atr_pct:     float, current ATR as fraction of price
            news_event:  bool (optional), True if high-impact news active

    Returns:
        {
            "score":    int (0-10),
            "approved": bool,
            "breakdown": {criterion: points_awarded},
        }
    """
    spread_pips = float(context.get("spread_pips", 999.0))
    atr_pct = float(context.get("atr_pct", 0.0))
    utc_hour = int(context.get("utc_hour", 0))

    breakdown: dict[str, int] = {
        "htf_bias_aligned": 0,
        "liquidity_event": 0,
        "structure_confirmation": 0,
        "active_session": 0,
        "spread_acceptable": 0,
        "volatility_acceptable": 0,
        "news_clear": 0,
    }

    if _htf_bias_aligned(signal, context):
        breakdown["htf_bias_aligned"] = 2

    if _has_liquidity_event(signal):
        breakdown["liquidity_event"] = 2

    if _has_structure_confirmation(signal):
        breakdown["structure_confirmation"] = 2

    if _in_active_session(signal, utc_hour):
        breakdown["active_session"] = 1

    if _spread_acceptable(signal, spread_pips):
        breakdown["spread_acceptable"] = 1

    if _volatility_acceptable(atr_pct):
        breakdown["volatility_acceptable"] = 1

    if _news_clear(context):
        breakdown["news_clear"] = 1

    score = sum(breakdown.values())
    approved = score >= MIN_SCORE

    return {
        "score": score,
        "approved": approved,
        "breakdown": breakdown,
    }
