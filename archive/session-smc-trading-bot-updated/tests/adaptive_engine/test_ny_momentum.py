"""Tests for bot/strategies/ny_momentum_strategy.py"""

import pytest
from adaptive.strategies import AdaptiveSignal
from adaptive.strategies.ny_momentum_strategy import generate_signals


def _ts(hour: int, minute: int = 0) -> str:
    return f"2026-06-24T{hour:02d}:{minute:02d}:00+00:00"


def _candle(hour: int, minute: int, open_: float, high: float,
            low: float, close: float) -> dict:
    return {
        "time":   _ts(hour, minute),
        "open":   open_,
        "high":   high,
        "low":    low,
        "close":  close,
        "volume": 1000,
    }


def _make_london_bars(london_high: float, london_low: float) -> list[dict]:
    mid = (london_high + london_low) / 2
    bars = []
    for h in range(6, 10):
        for m in (0, 15, 30, 45):
            bars.append(_candle(h, m, mid, london_high, london_low, mid))
    return bars


def _make_ny_sweep_long(london_high: float, london_low: float) -> list[dict]:
    """NY bars that sweep London High, then retest."""
    mid = (london_high + london_low) / 2
    bars = _make_london_bars(london_high, london_low)
    # Sweep candle
    bars.append(_candle(11, 0, mid, london_high + 0.0012, mid, london_high + 0.0005))
    # Retest candle
    bars.append(_candle(11, 15, london_high + 0.0003, london_high + 0.0003,
                        london_high - 0.0001, london_high - 0.0001))
    return bars


def _make_ny_sweep_short(london_high: float, london_low: float) -> list[dict]:
    """NY bars that sweep London Low, then retest."""
    mid = (london_high + london_low) / 2
    bars = _make_london_bars(london_high, london_low)
    # Sweep candle
    bars.append(_candle(11, 0, mid, mid, london_low - 0.0012, london_low - 0.0005))
    # Retest candle
    bars.append(_candle(11, 15, london_low - 0.0003, london_low + 0.0001,
                        london_low - 0.0003, london_low + 0.0001))
    return bars


LH = 1.1050
LL = 1.1000


class TestGenerateSignalsNY:
    def test_long_signal_on_sweep_and_retest(self):
        bars = _make_ny_sweep_long(LH, LL)
        signals = generate_signals(bars, "EURUSD")
        assert len(signals) >= 1
        sig = signals[0]
        assert sig.direction == "LONG"
        assert sig.strategy  == "ny_momentum"
        assert sig.session   == "new_york"

    def test_short_signal_on_sweep_and_retest(self):
        bars = _make_ny_sweep_short(LH, LL)
        signals = generate_signals(bars, "EURUSD")
        assert len(signals) >= 1
        sig = signals[0]
        assert sig.direction == "SHORT"

    def test_sl_below_london_low_for_long(self):
        bars = _make_ny_sweep_long(LH, LL)
        sig = generate_signals(bars, "EURUSD")[0]
        assert sig.sl_price < LL

    def test_sl_above_london_high_for_short(self):
        bars = _make_ny_sweep_short(LH, LL)
        sig = generate_signals(bars, "EURUSD")[0]
        assert sig.sl_price > LH

    def test_tp_at_2r_for_long(self):
        bars = _make_ny_sweep_long(LH, LL)
        sig = generate_signals(bars, "EURUSD")[0]
        risk   = sig.entry_price - sig.sl_price
        reward = sig.tp_price    - sig.entry_price
        assert reward == pytest.approx(risk * 2.0, rel=0.05)

    def test_metadata_has_london_levels(self):
        bars = _make_ny_sweep_long(LH, LL)
        sig = generate_signals(bars, "EURUSD")[0]
        assert "london_high" in sig.metadata
        assert "london_low"  in sig.metadata
        assert sig.metadata["liquidity_swept"] is True

    def test_no_signal_without_london_bars(self):
        bars = [_candle(11, 0, 1.1000, 1.1050, 1.0990, 1.1040)]
        assert generate_signals(bars, "EURUSD") == []

    def test_no_signal_without_ny_bars(self):
        bars = _make_london_bars(LH, LL)
        assert generate_signals(bars, "EURUSD") == []

    def test_no_sweep_no_signal(self):
        bars = _make_london_bars(LH, LL)
        mid = (LH + LL) / 2
        # NY bars that do not breach London High or Low
        for h in range(11, 15):
            bars.append(_candle(h, 0, mid, mid + 0.0010, mid - 0.0010, mid))
        assert generate_signals(bars, "EURUSD") == []

    def test_adaptive_signal_type(self):
        bars = _make_ny_sweep_long(LH, LL)
        sig = generate_signals(bars, "EURUSD")[0]
        assert isinstance(sig, AdaptiveSignal)
