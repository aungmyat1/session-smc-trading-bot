"""
Adaptive Session Engine v1 — NY Momentum Strategy.

Captures NY session expansion off London reference levels.

Logic:
  1. Identify London High / London Low from London session bars (06:00–09:00 UTC).
  2. During NY session (11:00–15:00 UTC), watch for price to sweep London High/Low.
  3. Confirm: 15M candle must CLOSE beyond the swept level.
  4. Wait for retest of the swept level.
  5. Entry on retest candle; SL on opposite London extreme; TP = 2R.

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

LONDON_START = 6
LONDON_END = 9  # inclusive
NY_START = 11
NY_END = 15  # inclusive

TP_RR = 2.0
SWEEP_BUFFER = 1  # pips — how much beyond the level counts as a sweep


def _utc_hour(candle: dict) -> int:
    t = candle.get("time")
    if isinstance(t, str):
        dt = datetime.fromisoformat(t.replace("Z", "+00:00"))
    elif isinstance(t, datetime):
        dt = t if t.tzinfo else t.replace(tzinfo=timezone.utc)
    else:
        return -1
    return dt.astimezone(timezone.utc).hour


def _build_london_levels(candles: list[dict]) -> dict | None:
    bars = [c for c in candles if LONDON_START <= _utc_hour(c) <= LONDON_END]
    if not bars:
        return None
    return {
        "high": max(c["high"] for c in bars),
        "low": min(c["low"] for c in bars),
    }


def generate_signals(
    candles_m15: list[dict],
    symbol: str,
) -> list[AdaptiveSignal]:
    """
    Scan M15 bars for NY Momentum setups.

    Args:
        candles_m15: M15 OHLCV dicts (ISO/datetime time field, UTC).
                     Must cover London session through NY session.
        symbol:      "EURUSD" | "GBPUSD" | "USDJPY".

    Returns:
        List of AdaptiveSignal. Empty if no valid setup.
    """
    pip = _PIP_SIZE.get(symbol, 0.0001)

    london = _build_london_levels(candles_m15)
    if london is None:
        return []

    lh, ll = london["high"], london["low"]
    signals: list[AdaptiveSignal] = []

    swept_long: bool = False
    swept_short: bool = False
    awaiting_retest_long: bool = False
    awaiting_retest_short: bool = False

    for candle in candles_m15:
        h = _utc_hour(candle)
        if h < NY_START or h > NY_END:
            continue

        close = candle["close"]
        high = candle["high"]
        low = candle["low"]
        t = candle.get("time", "")
        ts_str = (
            t
            if isinstance(t, str)
            else t.isoformat() if hasattr(t, "isoformat") else str(t)
        )

        # ── Sweep detection ──────────────────────────────────────────────────
        if not swept_long and not awaiting_retest_long:
            if high > lh + SWEEP_BUFFER * pip and close > lh:
                swept_long = True
                awaiting_retest_long = True

        if not swept_short and not awaiting_retest_short:
            if low < ll - SWEEP_BUFFER * pip and close < ll:
                swept_short = True
                awaiting_retest_short = True

        # ── Retest entry ─────────────────────────────────────────────────────
        if awaiting_retest_long:
            # Retest = bar that touches back to London High zone
            retest_top = lh + 2 * pip
            retest_bot = lh - 1 * pip
            if retest_bot <= low <= retest_top or retest_bot <= close <= retest_top:
                entry = close
                sl = ll - pip  # below London Low
                risk = entry - sl
                if risk > 0:
                    tp = entry + risk * TP_RR
                    signals.append(
                        AdaptiveSignal(
                            strategy="ny_momentum",
                            pair=symbol,
                            direction="LONG",
                            entry_price=entry,
                            sl_price=sl,
                            tp_price=tp,
                            session="new_york",
                            timestamp=ts_str,
                            reason="NY sweep London High + retest LONG",
                            metadata={
                                "london_high": lh,
                                "london_low": ll,
                                "liquidity_swept": True,
                                "structure_confirmed": True,
                            },
                        )
                    )
                awaiting_retest_long = False

        if awaiting_retest_short:
            retest_top = ll + 1 * pip
            retest_bot = ll - 2 * pip
            if retest_bot <= high <= retest_top or retest_bot <= close <= retest_top:
                entry = close
                sl = lh + pip  # above London High
                risk = sl - entry
                if risk > 0:
                    tp = entry - risk * TP_RR
                    signals.append(
                        AdaptiveSignal(
                            strategy="ny_momentum",
                            pair=symbol,
                            direction="SHORT",
                            entry_price=entry,
                            sl_price=sl,
                            tp_price=tp,
                            session="new_york",
                            timestamp=ts_str,
                            reason="NY sweep London Low + retest SHORT",
                            metadata={
                                "london_high": lh,
                                "london_low": ll,
                                "liquidity_swept": True,
                                "structure_confirmed": True,
                            },
                        )
                    )
                awaiting_retest_short = False

    return signals
