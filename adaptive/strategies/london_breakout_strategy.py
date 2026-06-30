"""
Adaptive Session Engine v1 — London Breakout Strategy.

Logic:
  1. Build Asian session range (00:00–06:00 UTC).
  2. Validate range: 15 pips ≤ range ≤ 50 pips.
  3. Signal fires when a 15M candle CLOSES above Asian High (LONG)
     or below Asian Low (SHORT) during London session (06:00–09:00 UTC).
  4. Wait for retest of the breakout level before confirming entry.
  5. SL = opposite side of Asian range; TP = 1.5R.

Pairs: EURUSD, GBPUSD, USDJPY
Output: AdaptiveSignal objects. No broker calls.

Public API:
    generate_signals(candles_m15, symbol) -> list[AdaptiveSignal]
"""

from __future__ import annotations

from datetime import datetime, timezone

from adaptive.strategies import AdaptiveSignal

_PIP_SIZE: dict[str, float] = {
    "EURUSD": 0.0001,
    "GBPUSD": 0.0001,
    "USDJPY": 0.01,
    "XAUUSD": 0.1,
}

ASIAN_START_HOUR = 0    # 00:00 UTC
ASIAN_END_HOUR   = 6    # 06:00 UTC (exclusive)
LONDON_START_HOUR = 6   # 06:00 UTC
LONDON_END_HOUR   = 9   # 09:00 UTC (inclusive)

MIN_RANGE_PIPS = 15.0
MAX_RANGE_PIPS = 50.0

TP_RR = 1.5
RETEST_TOLERANCE = 0.3  # fraction of pip — retest must come back within this


def _utc_hour(candle: dict) -> int:
    t = candle.get("time")
    if isinstance(t, str):
        dt = datetime.fromisoformat(t.replace("Z", "+00:00"))
    elif isinstance(t, datetime):
        dt = t if t.tzinfo else t.replace(tzinfo=timezone.utc)
    else:
        return -1
    return dt.astimezone(timezone.utc).hour


def _build_asian_range(candles: list[dict]) -> dict | None:
    """Compute the Asian session high/low from M15 bars."""
    bars = [c for c in candles if ASIAN_START_HOUR <= _utc_hour(c) < ASIAN_END_HOUR]
    if not bars:
        return None
    high = max(c["high"] for c in bars)
    low  = min(c["low"]  for c in bars)
    return {"high": high, "low": low}


def _range_pips(asian: dict, pip: float) -> float:
    return (asian["high"] - asian["low"]) / pip


def _is_london_bar(candle: dict) -> bool:
    return LONDON_START_HOUR <= _utc_hour(candle) <= LONDON_END_HOUR


def generate_signals(
    candles_m15: list[dict],
    symbol: str,
) -> list[AdaptiveSignal]:
    """
    Scan M15 bars for London Breakout setups.

    Args:
        candles_m15: M15 OHLCV dicts with 'time' key (ISO string or datetime, UTC).
                     Must cover at least the Asian session before the London window.
        symbol:      "EURUSD" | "GBPUSD" | "USDJPY".

    Returns:
        List of AdaptiveSignal. Empty if no valid setup.
    """
    pip = _PIP_SIZE.get(symbol, 0.0001)

    asian = _build_asian_range(candles_m15)
    if asian is None:
        return []

    rng_pips = _range_pips(asian, pip)
    if not (MIN_RANGE_PIPS <= rng_pips <= MAX_RANGE_PIPS):
        return []

    ah, al = asian["high"], asian["low"]
    signals: list[AdaptiveSignal] = []
    breakout_direction: str | None = None

    for candle in candles_m15:
        if not _is_london_bar(candle):
            continue

        close = candle["close"]
        t = candle.get("time", "")
        ts_str = t if isinstance(t, str) else t.isoformat() if hasattr(t, "isoformat") else str(t)

        # Detect breakout close
        if breakout_direction is None:
            if close > ah:
                breakout_direction = "LONG"
            elif close < al:
                breakout_direction = "SHORT"
            continue

        # After breakout: wait for retest
        if breakout_direction == "LONG":
            # Retest = price pulls back close to Asian High
            retest_zone_top = ah + RETEST_TOLERANCE * pip
            retest_zone_bot = ah - 2 * pip
            if retest_zone_bot <= candle["low"] <= retest_zone_top:
                entry = candle["close"]
                sl    = al - pip                      # below Asian Low
                risk  = entry - sl
                if risk <= 0:
                    breakout_direction = None
                    continue
                tp = entry + risk * TP_RR
                signals.append(AdaptiveSignal(
                    strategy    = "london_breakout",
                    pair        = symbol,
                    direction   = "LONG",
                    entry_price = entry,
                    sl_price    = sl,
                    tp_price    = tp,
                    session     = "london",
                    timestamp   = ts_str,
                    reason      = f"Asian breakout LONG; range {rng_pips:.1f} pips",
                    metadata    = {
                        "asian_high":   ah,
                        "asian_low":    al,
                        "range_pips":   rng_pips,
                        "liquidity_swept":     False,
                        "structure_confirmed": True,
                    },
                ))
                breakout_direction = None  # one signal per session

        elif breakout_direction == "SHORT":
            retest_zone_top = al + 2 * pip
            retest_zone_bot = al - RETEST_TOLERANCE * pip
            if retest_zone_bot <= candle["high"] <= retest_zone_top:
                entry = candle["close"]
                sl    = ah + pip                      # above Asian High
                risk  = sl - entry
                if risk <= 0:
                    breakout_direction = None
                    continue
                tp = entry - risk * TP_RR
                signals.append(AdaptiveSignal(
                    strategy    = "london_breakout",
                    pair        = symbol,
                    direction   = "SHORT",
                    entry_price = entry,
                    sl_price    = sl,
                    tp_price    = tp,
                    session     = "london",
                    timestamp   = ts_str,
                    reason      = f"Asian breakout SHORT; range {rng_pips:.1f} pips",
                    metadata    = {
                        "asian_high":   ah,
                        "asian_low":    al,
                        "range_pips":   rng_pips,
                        "liquidity_swept":     False,
                        "structure_confirmed": True,
                    },
                ))
                breakout_direction = None

    return signals
