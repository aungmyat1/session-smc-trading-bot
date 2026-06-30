"""Tests for bot/strategies/london_breakout_strategy.py"""

from datetime import datetime, timezone

import pytest

from adaptive.strategies import AdaptiveSignal
from adaptive.strategies.london_breakout_strategy import generate_signals


def _ts(hour: int, minute: int = 0) -> str:
    return f"2026-06-24T{hour:02d}:{minute:02d}:00+00:00"


def _candle(
    hour: int, minute: int, open_: float, high: float, low: float, close: float
) -> dict:
    return {
        "time": _ts(hour, minute),
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": 1000,
    }


def _make_asian_candles(asian_high: float, asian_low: float) -> list[dict]:
    """Create 24 Asian session bars (00:00-05:45 UTC) with given H/L."""
    bars = []
    mid = (asian_high + asian_low) / 2
    for h in range(0, 6):
        for m in (0, 15, 30, 45):
            bars.append(_candle(h, m, mid, asian_high, asian_low, mid))
    return bars


def _make_london_breakout_long(asian_high: float, asian_low: float) -> list[dict]:
    """Asian bars + London bar that closes above Asian High + retest bar."""
    mid = (asian_high + asian_low) / 2
    breakout_close = asian_high + 0.0005
    bars = _make_asian_candles(asian_high, asian_low)
    # London breakout candle
    bars.append(_candle(6, 0, mid, asian_high + 0.001, mid, breakout_close))
    # Retest candle — pulls back to Asian High
    bars.append(
        _candle(
            6,
            15,
            breakout_close,
            breakout_close,
            asian_high - 0.0001,
            asian_high + 0.00005,
        )
    )
    return bars


def _make_london_breakout_short(asian_high: float, asian_low: float) -> list[dict]:
    """Asian bars + London bar closing below Asian Low + retest bar."""
    mid = (asian_high + asian_low) / 2
    breakout_close = asian_low - 0.0005
    bars = _make_asian_candles(asian_high, asian_low)
    # London breakout candle
    bars.append(_candle(6, 0, mid, mid, asian_low - 0.001, breakout_close))
    # Retest candle — pulls back to Asian Low
    bars.append(
        _candle(
            6,
            15,
            breakout_close,
            asian_low + 0.0001,
            asian_low - 0.00005,
            asian_low - 0.00005,
        )
    )
    return bars


ASIAN_HIGH = 1.1030
ASIAN_LOW = 1.1000  # 30 pip range — valid


class TestGenerateSignals:
    def test_returns_long_signal_on_valid_breakout(self):
        bars = _make_london_breakout_long(ASIAN_HIGH, ASIAN_LOW)
        signals = generate_signals(bars, "EURUSD")
        assert len(signals) == 1
        sig = signals[0]
        assert sig.direction == "LONG"
        assert sig.strategy == "london_breakout"
        assert sig.pair == "EURUSD"
        assert sig.session == "london"

    def test_returns_short_signal_on_valid_breakout(self):
        bars = _make_london_breakout_short(ASIAN_HIGH, ASIAN_LOW)
        signals = generate_signals(bars, "EURUSD")
        assert len(signals) == 1
        sig = signals[0]
        assert sig.direction == "SHORT"

    def test_sl_below_asian_low_for_long(self):
        bars = _make_london_breakout_long(ASIAN_HIGH, ASIAN_LOW)
        sig = generate_signals(bars, "EURUSD")[0]
        assert sig.sl_price < ASIAN_LOW

    def test_sl_above_asian_high_for_short(self):
        bars = _make_london_breakout_short(ASIAN_HIGH, ASIAN_LOW)
        sig = generate_signals(bars, "EURUSD")[0]
        assert sig.sl_price > ASIAN_HIGH

    def test_tp_at_1_5r_for_long(self):
        bars = _make_london_breakout_long(ASIAN_HIGH, ASIAN_LOW)
        sig = generate_signals(bars, "EURUSD")[0]
        risk = sig.entry_price - sig.sl_price
        reward = sig.tp_price - sig.entry_price
        assert reward == pytest.approx(risk * 1.5, rel=0.01)

    def test_no_signal_when_asian_range_too_small(self):
        # 5 pip range — below minimum of 15
        high = 1.1005
        low = 1.1000
        bars = _make_london_breakout_long(high, low)
        assert generate_signals(bars, "EURUSD") == []

    def test_no_signal_when_asian_range_too_large(self):
        # 60 pip range — above maximum of 50
        high = 1.1060
        low = 1.1000
        bars = _make_london_breakout_long(high, low)
        assert generate_signals(bars, "EURUSD") == []

    def test_no_signal_with_no_asian_bars(self):
        # Only London bars, no Asian session
        bars = [_candle(7, 0, 1.1000, 1.1020, 1.0990, 1.1015)]
        assert generate_signals(bars, "EURUSD") == []

    def test_signal_metadata_contains_range_pips(self):
        bars = _make_london_breakout_long(ASIAN_HIGH, ASIAN_LOW)
        sig = generate_signals(bars, "EURUSD")[0]
        assert "range_pips" in sig.metadata
        assert sig.metadata["range_pips"] == pytest.approx(30.0, rel=0.01)

    def test_adaptive_signal_type(self):
        bars = _make_london_breakout_long(ASIAN_HIGH, ASIAN_LOW)
        sig = generate_signals(bars, "EURUSD")[0]
        assert isinstance(sig, AdaptiveSignal)
