"""
Unit tests for strategies/smc_lss/displacement.py — synthetic candles only.

Covers: wilder_atr seed + recursive smoothing, the displacement body gate
(>= 1.5xATR), the close-quartile gate (edge-inclusive, >=/<=), and
rejection paths (ATR unavailable/zero, zero-range candle, invalid candle).
"""

from __future__ import annotations

import pytest

from strategies.smc_lss.displacement import detect_displacement, wilder_atr


def _bar(o, h, l, c):
    return {"open": o, "high": h, "low": l, "close": c}


class TestWilderATR:
    def test_warmup_indices_are_none(self):
        candles = [_bar(10, 11, 9, 10.5), _bar(10.5, 12, 10, 11)]
        atrs = wilder_atr(candles, period=2)
        assert atrs == [None, None]

    def test_seed_and_recursive_values(self):
        candles = [
            _bar(9, 10, 8, 9),
            _bar(9, 12, 9, 11),
            _bar(11, 12, 10, 11),
            _bar(11, 14, 11, 13),
            _bar(13, 13, 12, 12),
        ]
        atrs = wilder_atr(candles, period=2)
        assert atrs[0] is None
        assert atrs[1] is None
        assert atrs[2] == pytest.approx(2.5)     # seed = mean(TR1=3, TR2=2)
        assert atrs[3] == pytest.approx(2.75)    # (2.5*1 + TR3=3) / 2
        assert atrs[4] == pytest.approx(1.875)   # (2.75*1 + TR4=1) / 2

    def test_insufficient_candles_returns_all_none(self):
        candles = [_bar(9, 10, 8, 9), _bar(9, 12, 9, 11)]
        assert wilder_atr(candles, period=14) == [None, None]


class TestDetectDisplacement:
    def test_bullish_displacement_detected(self):
        candle = _bar(10.0, 12.5, 10.0, 12.0)  # body=2.0, range=2.5, close_pos=0.8
        result = detect_displacement(candle, atr=1.0, direction="long", body_atr_mult=1.5)
        assert result.detected is True
        assert result.side == "long"
        assert result.reason == "bullish_displacement"

    def test_bearish_displacement_detected(self):
        candle = _bar(12.0, 12.5, 10.0, 10.5)  # body=1.5, range=2.5, close_pos=0.2
        result = detect_displacement(candle, atr=1.0, direction="short", body_atr_mult=1.5)
        assert result.detected is True
        assert result.side == "short"
        assert result.reason == "bearish_displacement"

    def test_body_exactly_at_threshold_passes(self):
        candle = _bar(10.0, 11.5, 10.0, 11.5)  # body=1.5, close_pos=1.0
        result = detect_displacement(candle, atr=1.0, direction="long", body_atr_mult=1.5)
        assert result.detected is True

    def test_close_position_exactly_at_quartile_passes(self):
        candle = _bar(10.0, 14.0, 10.0, 13.0)  # body=3.0, range=4.0, close_pos=0.75 exactly
        result = detect_displacement(candle, atr=1.0, direction="long", body_atr_mult=1.0)
        assert result.detected is True

    def test_body_below_threshold_fails(self):
        candle = _bar(10.0, 11.49, 10.0, 11.49)  # body=1.49 < 1.5
        result = detect_displacement(candle, atr=1.0, direction="long", body_atr_mult=1.5)
        assert result.detected is False
        assert "body" in result.reason

    def test_close_position_below_quartile_fails(self):
        candle = _bar(10.0, 14.0, 10.0, 12.9)  # body=2.9, close_pos=0.725 < 0.75
        result = detect_displacement(candle, atr=1.0, direction="long", body_atr_mult=1.0)
        assert result.detected is False

    def test_atr_none_rejected(self):
        candle = _bar(10.0, 12.5, 10.0, 12.0)
        result = detect_displacement(candle, atr=None, direction="long")
        assert result.detected is False
        assert result.reason == "atr_unavailable"

    def test_atr_zero_rejected(self):
        candle = _bar(10.0, 12.5, 10.0, 12.0)
        result = detect_displacement(candle, atr=0.0, direction="long")
        assert result.detected is False
        assert result.reason == "atr_zero"

    def test_zero_range_candle_rejected(self):
        candle = _bar(10.0, 10.0, 10.0, 10.0)
        result = detect_displacement(candle, atr=1.0, direction="long")
        assert result.detected is False
        assert result.reason == "zero_range_candle"

    def test_invalid_candle_rejected(self):
        result = detect_displacement({"open": "bad"}, atr=1.0, direction="long")
        assert result.detected is False
        assert result.reason == "invalid_candle"
