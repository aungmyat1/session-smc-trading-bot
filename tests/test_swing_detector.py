"""Tests for session_smc/swing_detector.py"""
from session_smc.swing_detector import (
    swing_highs,
    swing_lows,
    last_swing_high,
    last_swing_low,
    classify_structure,
)


def c(h, l, o=None, cl=None):
    """Build a minimal candle dict."""
    return {"high": h, "low": l, "open": o or l, "close": cl or h, "time": "T"}


# ── swing_highs ───────────────────────────────────────────────────────────────

class TestSwingHighs:
    def test_too_few_candles_returns_empty(self):
        candles = [c(1, 0), c(2, 0), c(3, 0)]  # need 2n+1 = 7 for n=3
        assert swing_highs(candles, n=3) == []

    def test_single_peak_n1(self):
        # highs: 1, 3, 1 → peak at index 1
        candles = [c(1, 0), c(3, 0), c(1, 0)]
        assert swing_highs(candles, n=1) == [1]

    def test_single_peak_n3(self):
        # highs: 1,1,1, 5, 1,1,1
        candles = [c(1, 0)] * 3 + [c(5, 0)] + [c(1, 0)] * 3
        assert swing_highs(candles, n=3) == [3]

    def test_equal_highs_not_swing(self):
        # highs: 1, 2, 2, 1 — equal highs at 1 and 2 → neither is strict
        candles = [c(1, 0), c(2, 0), c(2, 0), c(1, 0)]
        assert swing_highs(candles, n=1) == []

    def test_multiple_peaks(self):
        # highs: 1, 3, 1, 4, 1
        candles = [c(1, 0), c(3, 0), c(1, 0), c(4, 0), c(1, 0)]
        idxs = swing_highs(candles, n=1)
        assert 1 in idxs and 3 in idxs

    def test_last_n_bars_unconfirmed(self):
        # With n=2, last 2 bars cannot be a swing
        candles = [c(1, 0), c(1, 0), c(5, 0), c(1, 0), c(6, 0)]
        # Index 4 = 6.0 — needs bars at 5 and 6 but they don't exist → NOT returned
        idxs = swing_highs(candles, n=2)
        assert 4 not in idxs

    def test_no_peak(self):
        # Monotone increasing — no swing high
        candles = [c(i, 0) for i in range(7)]
        assert swing_highs(candles, n=3) == []

    def test_descending_no_swing(self):
        candles = [c(7 - i, 0) for i in range(7)]
        assert swing_highs(candles, n=3) == []


# ── swing_lows ────────────────────────────────────────────────────────────────

class TestSwingLows:
    def test_single_trough_n1(self):
        candles = [c(10, 5), c(10, 2), c(10, 5)]
        assert swing_lows(candles, n=1) == [1]

    def test_single_trough_n3(self):
        candles = [c(10, 5)] * 3 + [c(10, 1)] + [c(10, 5)] * 3
        assert swing_lows(candles, n=3) == [3]

    def test_equal_lows_not_swing(self):
        candles = [c(5, 3), c(5, 2), c(5, 2), c(5, 3)]
        assert swing_lows(candles, n=1) == []

    def test_last_n_unconfirmed(self):
        candles = [c(5, 3), c(5, 3), c(5, 1), c(5, 3), c(5, 0)]
        # index 4 (low=0) needs bars 5 and 6 → not returned with n=2
        idxs = swing_lows(candles, n=2)
        assert 4 not in idxs


# ── last_swing_high / last_swing_low ─────────────────────────────────────────

class TestLastSwing:
    def _candles(self):
        # highs:  1, 3, 1, 2, 1, 4, 1
        # swing highs (n=1): index 1 (3.0), index 3 (2.0), index 5 (4.0)
        highs = [1, 3, 1, 2, 1, 4, 1]
        return [c(h, 0) for h in highs]

    def test_last_swing_high_no_limit(self):
        # Full slice → last swing high is at idx 5 (value 4)
        cd = self._candles()
        r = last_swing_high(cd, n=1)
        assert r is not None and r["index"] == 5 and r["price"] == 4

    def test_last_swing_high_before_idx(self):
        # before_idx=5 → subset [0:5] highs [1,3,1,2,1]
        # swing_highs([1,3,1,2,1], n=1) → indices [1, 3]
        cd = self._candles()
        r = last_swing_high(cd, n=1, before_idx=5)
        assert r is not None and r["index"] == 3 and r["price"] == 2

    def test_last_swing_high_too_short(self):
        # before_idx=2 → subset [0:2] → too few for n=1 (need 3)
        cd = self._candles()
        r = last_swing_high(cd, n=1, before_idx=2)
        assert r is None

    def test_last_swing_low_no_limit(self):
        # lows: 1, 3, 1, 2, 1, 4, 1 → swing lows (n=1): idx 0? no, idx 2 (1), idx 4 (1)
        # candles: lows = [3, 1, 3, 1, 3, 1, 3]
        lows = [3, 1, 3, 1, 3, 1, 3]
        cd = [c(5, lo) for lo in lows]
        r = last_swing_low(cd, n=1)
        assert r is not None and r["index"] == 5


# ── classify_structure ────────────────────────────────────────────────────────

class TestClassifyStructure:
    def _bullish_candles(self):
        # Two confirmed swing highs (HH) and two confirmed swing lows (HL) with n=1
        # highs: 1,2,1,3,1  lows: 1,0.5,1,0.7,1
        highs = [1, 2, 1, 3, 1]
        lows  = [1, 0.5, 1, 0.7, 1]
        return [c(h, l) for h, l in zip(highs, lows)]

    def _bearish_candles(self):
        # LL + LH: peaks at 5→4→3, valleys at 1.5→1.0
        # swing_highs n=1: idx 1(5), idx 3(4), idx 5(3)  → LH ✓
        # swing_lows  n=1: idx 2(1.5), idx 4(1.0)        → LL ✓
        highs = [1.0, 5.0, 2.0, 4.0, 1.5, 3.0, 1.0]
        lows  = [0.5, 4.0, 1.5, 3.0, 1.0, 2.0, 0.5]
        return [c(h, l) for h, l in zip(highs, lows)]

    def test_bullish_structure(self):
        assert classify_structure(self._bullish_candles(), n=1) == "bullish"

    def test_bearish_structure(self):
        assert classify_structure(self._bearish_candles(), n=1) == "bearish"

    def test_neutral_too_few_swings(self):
        # Only 1 swing high possible → neutral
        cd = [c(1, 0), c(3, 0), c(1, 0)]
        assert classify_structure(cd, n=1) == "neutral"

    def test_neutral_mixed(self):
        # HH but LL → mixed
        highs = [1, 2, 1, 3, 1]
        lows  = [1, 0.8, 1, 0.5, 1]
        cd = [c(h, l) for h, l in zip(highs, lows)]
        result = classify_structure(cd, n=1)
        # HH: 2→3 ✓, HL: 0.8→0.5 ✗ (LL instead) → 'neutral'
        assert result == "neutral"

    def test_before_idx_cuts_off(self):
        # Same bullish candles but before_idx=3 should not have enough swings
        cd = self._bullish_candles()
        r = classify_structure(cd, n=1, before_idx=3)
        # subset [0:3] = highs [1,2,1] → 1 swing high at idx 1 only → neutral
        assert r == "neutral"
