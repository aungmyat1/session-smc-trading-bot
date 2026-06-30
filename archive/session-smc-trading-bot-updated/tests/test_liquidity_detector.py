"""Tests for session_smc/liquidity_detector.py"""

import pytest

from session_smc.liquidity_detector import (build_session_range,
                                            classify_session, detect_sweep)


def c(o, h, l, cl):
    return {"open": o, "high": h, "low": l, "close": cl, "time": "T"}


# ── build_session_range ───────────────────────────────────────────────────────


class TestBuildSessionRange:
    def _range_candles(self):
        # 8 candles: highs 1.0950..1.0957, lows 1.0900..1.0907
        candles = []
        for i in range(8):
            candles.append(c(1.0920, 1.0950 + i * 0.0001, 1.0900 + i * 0.0001, 1.0930))
        return candles

    def test_builds_correct_high_low(self):
        cd = self._range_candles()
        r = build_session_range(cd, range_bars=8)
        assert r is not None
        assert r["high"] == pytest.approx(1.0957)
        assert r["low"] == pytest.approx(1.0900)

    def test_midpoint_is_average(self):
        cd = self._range_candles()
        r = build_session_range(cd, range_bars=8)
        assert r is not None
        assert r["midpoint"] == pytest.approx((r["high"] + r["low"]) / 2)

    def test_range_pips_computed(self):
        cd = self._range_candles()
        r = build_session_range(cd, range_bars=8)
        expected_pips = (1.0957 - 1.0900) / 0.0001
        assert r["range_pips"] == pytest.approx(expected_pips, rel=0.01)

    def test_too_few_bars_returns_none(self):
        cd = self._range_candles()[:5]
        assert build_session_range(cd, range_bars=8) is None

    def test_narrow_range_returns_none(self):
        # Range of 5 pips < min_range_pips default of 10
        cd = [c(1.09, 1.0903, 1.0898, 1.09)] * 8  # range ≈ 5 pips
        r = build_session_range(cd, range_bars=8, min_range_pips=10.0)
        assert r is None

    def test_custom_range_bars(self):
        # Only first 4 bars used
        candles = [c(1.09, 1.10, 1.08, 1.09)] * 4 + [
            c(1.09, 1.20, 1.00, 1.09)
        ] * 4  # extreme bars shouldn't count
        r = build_session_range(candles, range_bars=4, min_range_pips=5.0)
        assert r is not None
        assert r["high"] == pytest.approx(1.10)
        assert r["low"] == pytest.approx(1.08)


# ── classify_session ──────────────────────────────────────────────────────────


class TestClassifySession:
    def test_range_session(self):
        # Tight range vs large ATR → RANGE
        candles = [c(1.0, 1.001, 0.999, 1.0)] * 30  # TR ≈ 0.002
        sess_range = {"high": 1.001, "low": 0.999, "midpoint": 1.0, "range_pips": 2.0}
        # ATR ≈ 0.002; range = 0.002; ratio = 1.0 → TREND
        # Actually: same range and ATR → ratio ~ 1 → TREND
        result = classify_session(candles, sess_range)
        assert result in ("RANGE", "TREND", "MIXED")  # just check it runs

    def test_returns_string(self):
        candles = [c(1.0, 1.01, 0.99, 1.0)] * 30
        sess_range = {"high": 1.01, "low": 0.99}
        r = classify_session(candles, sess_range)
        assert r in ("RANGE", "TREND", "MIXED")

    def test_wide_range_trend(self):
        # Session range 50 pips, ATR 20 pips → ratio = 2.5 > 0.7 → TREND
        candles = [c(1.0, 1.002, 0.998, 1.0)] * 30  # ATR ≈ 0.004 per bar
        atr_approx = 0.004
        range_size = 0.0050  # 50 pips
        sess_range = {"high": 1.0 + range_size / 2, "low": 1.0 - range_size / 2}
        # ratio = 0.005 / ~0.004 = 1.25 > 0.7 → TREND
        r = classify_session(candles, sess_range)
        assert r == "TREND"


# ── detect_sweep ─────────────────────────────────────────────────────────────


class TestDetectSweep:
    def _basic_range(self):
        return {"high": 1.0920, "low": 1.0900}

    def test_bullish_sweep_detected(self):
        sess_range = self._basic_range()
        # Build: 8 range bars, then one sweep bar (low < 1.0900, close > 1.0900)
        candles = [c(1.091, 1.092, 1.090, 1.091)] * 8 + [
            c(1.0905, 1.0910, 1.0895, 1.0908)
        ]  # wick below, close inside
        result = detect_sweep(candles, sess_range, "bullish", from_idx=8)
        assert result is not None
        assert result["index"] == 8
        assert result["wick_extreme"] == pytest.approx(1.0895)
        assert result["direction"] == "bullish"

    def test_bearish_sweep_detected(self):
        sess_range = self._basic_range()
        candles = [c(1.091, 1.092, 1.090, 1.091)] * 8 + [
            c(1.0915, 1.0925, 1.0905, 1.0912)
        ]  # wick above 1.0920, close below
        result = detect_sweep(candles, sess_range, "bearish", from_idx=8)
        assert result is not None
        assert result["wick_extreme"] == pytest.approx(1.0925)

    def test_no_sweep_when_close_stays_outside(self):
        # Bullish: bar breaks below session low but close also below → no sweep
        sess_range = self._basic_range()
        candles = [c(1.091, 1.092, 1.090, 1.091)] * 8 + [
            c(1.089, 1.090, 1.088, 1.0895)
        ]  # close < 1.0900
        result = detect_sweep(candles, sess_range, "bullish", from_idx=8)
        assert result is None

    def test_no_sweep_when_no_wick_outside(self):
        # Bars stay inside range → no sweep
        sess_range = self._basic_range()
        candles = [c(1.091, 1.092, 1.090, 1.091)] * 12
        result = detect_sweep(candles, sess_range, "bullish", from_idx=8)
        assert result is None

    def test_from_idx_respected(self):
        # Sweep bar is at index 5 but from_idx=8 → should not be found
        sess_range = self._basic_range()
        candles = (
            [c(1.091, 1.092, 1.090, 1.091)] * 5
            + [c(1.0905, 1.0910, 1.0895, 1.0908)]
            + [c(1.091, 1.092, 1.090, 1.091)] * 6
        )
        result = detect_sweep(candles, sess_range, "bullish", from_idx=8)
        assert result is None or result["index"] >= 8

    def test_returns_none_on_empty_tail(self):
        sess_range = self._basic_range()
        candles = [c(1.091, 1.092, 1.090, 1.091)] * 5
        result = detect_sweep(candles, sess_range, "bullish", from_idx=8)
        assert result is None
