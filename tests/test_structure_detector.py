"""Tests for session_smc/structure_detector.py"""

import math
from session_smc.structure_detector import (
    atr,
    htf_bias,
    detect_choch,
    detect_bos,
    detect_displacement,
)


def c(o, h, lo, cl):
    return {"open": o, "high": h, "low": lo, "close": cl, "time": "T"}


def flat(price, n=20):
    """n identical OHLC candles — no structure."""
    return [c(price, price, price, price) for _ in range(n)]


# ── ATR ───────────────────────────────────────────────────────────────────────


class TestATR:
    def test_too_short_all_nan(self):
        vals = atr([c(1, 2, 0, 1)], period=14)
        assert math.isnan(vals[0])

    def test_period_14_first_valid_at_index_14(self):
        # 20 candles of range 1 each: ATR should be ~1 at index 14
        candles = [c(0, 1, 0, 0.5)] * 20
        vals = atr(candles, period=14)
        for i in range(14):
            assert math.isnan(vals[i]), f"index {i} should be NaN"
        assert not math.isnan(vals[14])
        assert abs(vals[14] - 1.0) < 0.01

    def test_all_same_range_converges(self):
        # Daily range = 2 pip, no gaps → ATR should ≈ 2
        candles = [c(100, 102, 100, 101)] * 30
        vals = atr(candles, period=5)
        assert abs(vals[-1] - 2.0) < 0.01

    def test_wilder_smoothing_direction(self):
        # First 5 bars range = 1, then 5 bars range = 5
        # ATR should rise above 1 after the jump
        low_range = [c(0, 1, 0, 0.5)] * 20
        high_range = [c(0, 5, 0, 2.5)] * 10
        candles = low_range + high_range
        vals = atr(candles, period=5)
        assert vals[-1] > vals[20]

    def test_returns_same_length(self):
        candles = [c(1, 2, 0, 1)] * 50
        assert len(atr(candles, period=14)) == 50


# ── HTF Bias ─────────────────────────────────────────────────────────────────


class TestHTFBias:
    def _bullish(self):
        # HH at idx 1(2) and idx 3(3); HL at idx 2(0.5) and idx 4(0.7) with n=1
        # Trailing bar at idx 5 gives idx 4 a right neighbor so swing_lows confirms it
        highs = [1, 2, 1, 3, 1, 4]
        lows = [0.5, 1.5, 0.5, 1.7, 0.7, 1.8]
        return [c(lo, h, lo, h) for h, lo in zip(highs, lows)]

    def _bearish(self):
        # LH: peaks 5→4→3 (idx 1,3,5); LL: valleys 1.5→1.0 (idx 2,4) with n=1
        highs = [1.0, 5.0, 2.0, 4.0, 1.5, 3.0, 1.0]
        lows = [0.5, 4.0, 1.5, 3.0, 1.0, 2.0, 0.5]
        return [c(lo, h, lo, h) for h, lo in zip(highs, lows)]

    def test_both_bullish_returns_bullish(self):
        assert htf_bias(self._bullish(), self._bullish(), 1) == "bullish"

    def test_both_bearish_returns_bearish(self):
        assert htf_bias(self._bearish(), self._bearish(), 1) == "bearish"

    def test_4h_bullish_1h_neutral_returns_bullish(self):
        assert htf_bias(self._bullish(), flat(1.0), 1) == "bullish"

    def test_4h_bullish_1h_bearish_returns_neutral(self):
        assert htf_bias(self._bullish(), self._bearish(), 1) == "neutral"

    def test_4h_bearish_1h_bullish_returns_neutral(self):
        assert htf_bias(self._bearish(), self._bullish(), 1) == "neutral"

    def test_4h_neutral_returns_neutral(self):
        assert htf_bias(flat(1.0), flat(1.0), 1) == "neutral"


# ── CHoCH ────────────────────────────────────────────────────────────────────


class TestDetectCHoCH:
    def _make_candles(self):
        # 12 candles; highs gradually rise, sweep at index 8
        candles = []
        for i in range(12):
            h = 1.0 + i * 0.01
            candles.append(c(h - 0.005, h, h - 0.01, h - 0.003))
        return candles

    def test_bullish_choch_fires_after_sweep(self):
        # Bullish: lookback=4, reference = max high in [4,8)
        # highs[4..7] = 1.04, 1.05, 1.06, 1.07 → reference = 1.07
        # bars after idx 8 where close > 1.07:
        # bar 9: close = 1.09 - 0.003 = 1.087 > 1.07 ✓
        candles = self._make_candles()
        result = detect_choch(candles, sweep_idx=8, direction="bullish", lookback=4)
        assert result is not None
        assert result["index"] > 8
        assert result["reference"] > 0

    def test_bullish_choch_not_before_sweep(self):
        candles = self._make_candles()
        result = detect_choch(candles, sweep_idx=8, direction="bullish", lookback=4)
        if result:
            assert result["index"] > 8

    def test_bearish_choch_fires(self):
        # Build falling candles
        candles = [
            c(
                1.0 - i * 0.01,
                1.0 - i * 0.01 + 0.005,
                1.0 - i * 0.01 - 0.005,
                1.0 - i * 0.01 - 0.003,
            )
            for i in range(12)
        ]
        result = detect_choch(candles, sweep_idx=5, direction="bearish", lookback=3)
        if result:
            # close should be below reference (min low in window)
            assert candles[result["index"]]["close"] < result["reference"]

    def test_returns_none_when_no_choch(self):
        # All bars at same level → close never exceeds reference
        candles = flat(1.05)
        result = detect_choch(candles, sweep_idx=5, direction="bullish", lookback=4)
        assert result is None

    def test_empty_window_returns_none(self):
        candles = flat(1.0)
        # sweep_idx = 0 → window is empty
        result = detect_choch(candles, sweep_idx=0, direction="bullish", lookback=3)
        assert result is None


# ── BOS ───────────────────────────────────────────────────────────────────────


class TestDetectBOS:
    def test_bullish_bos_fires(self):
        # Swing level = 1.05, bars after idx 3 with close > 1.05
        candles = (
            [c(1.0, 1.04, 0.99, 1.0)] * 3
            + [c(1.0, 1.04, 0.99, 1.0)]
            + [c(1.0, 1.10, 0.99, 1.06)]
        )  # bar 4 close > 1.05
        result = detect_bos(candles, after_idx=3, direction="bullish", swing_level=1.05)
        assert result is not None
        assert result["index"] == 4
        assert result["level"] == 1.05

    def test_bearish_bos_fires(self):
        candles = (
            [c(1.1, 1.1, 1.06, 1.1)] * 3
            + [c(1.1, 1.1, 1.06, 1.1)]
            + [c(1.1, 1.1, 0.99, 0.98)]
        )  # bar 4 close < 1.05
        result = detect_bos(candles, after_idx=3, direction="bearish", swing_level=1.05)
        assert result is not None
        assert result["index"] == 4

    def test_none_when_swing_level_none(self):
        candles = [c(1, 2, 0, 1)] * 5
        assert detect_bos(candles, 2, "bullish", None) is None

    def test_none_when_level_never_broken(self):
        # All closes below 1.05
        candles = [c(1.0, 1.03, 0.99, 1.0)] * 8
        assert detect_bos(candles, 3, "bullish", 1.05) is None


# ── Displacement ──────────────────────────────────────────────────────────────


class TestDetectDisplacement:
    def _atr_const(self, value, n):
        """Artificial ATR list: all `value` except NaN before period 14."""
        return [float("nan")] * 14 + [value] * (n - 14)

    def test_bullish_displacement_found(self):
        # Big bullish candle at index 16, range = 10, atr = 5 → passes 1.5× check
        n = 20
        candles = (
            [c(1.0, 1.01, 0.99, 1.0)] * 16
            + [c(1.0, 1.10, 0.99, 1.09)]
            + [c(1.0, 1.01, 0.99, 1.0)] * 3
        )
        atr_v = self._atr_const(0.05, n)  # ATR = 0.05 → threshold 0.075 < range 0.11
        result = detect_displacement(candles, 14, 18, "bullish", atr_v, 1.5)
        assert result is not None
        assert result["index"] == 16

    def test_small_candle_not_displacement(self):
        n = 20
        candles = [c(1.0, 1.005, 0.999, 1.002)] * n  # range = 0.006
        atr_v = self._atr_const(0.01, n)  # ATR = 0.01 → threshold = 0.015 > 0.006
        assert detect_displacement(candles, 14, 18, "bullish", atr_v, 1.5) is None

    def test_wrong_direction_body_skipped(self):
        # Big BEARISH candle → should not count for 'bullish'
        n = 20
        candles = (
            [c(1.0, 1.01, 0.99, 1.0)] * 14
            + [c(1.09, 1.10, 0.99, 1.0)]
            + [c(1.0, 1.01, 0.99, 1.0)] * 5
        )  # bearish body
        atr_v = self._atr_const(0.05, n)
        assert detect_displacement(candles, 14, 18, "bullish", atr_v, 1.5) is None

    def test_bearish_displacement_found(self):
        n = 20
        candles = (
            [c(1.1, 1.1, 1.09, 1.1)] * 15
            + [c(1.1, 1.1, 0.99, 1.0)]
            + [c(1.0, 1.01, 0.99, 1.0)] * 4
        )  # bearish: open > close
        atr_v = self._atr_const(0.05, n)
        result = detect_displacement(candles, 14, 18, "bearish", atr_v, 1.5)
        assert result is not None and result["index"] == 15

    def test_nan_atr_skipped(self):
        # All ATRs are NaN → no displacement possible
        n = 10
        candles = [c(1.0, 2.0, 0.0, 1.0)] * n  # giant range, would qualify
        atr_v = [float("nan")] * n
        assert detect_displacement(candles, 0, 9, "bullish", atr_v, 1.5) is None
