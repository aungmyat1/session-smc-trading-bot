"""Tests for session_smc/poi_detector.py"""
import pytest
from session_smc.poi_detector import find_fvg, check_fvg_retest


def c(o, h, lo, cl):
    return {"open": o, "high": h, "low": lo, "close": cl, "time": "T"}


# ── find_fvg ─────────────────────────────────────────────────────────────────

class TestFindFVG:
    # Bullish FVG:
    # prev.high = 1.0900, disp candle, next.low = 1.0910
    # Gap: 1.0900 < 1.0910  ✓

    def _bull_candles(self):
        # idx 0: prev; idx 1: displacement; idx 2: next
        return [
            c(1.088, 1.0900, 1.088, 1.090),   # prev: high = 1.0900
            c(1.090, 1.095, 1.089, 1.094),    # displacement
            c(1.094, 1.096, 1.0910, 1.095),   # next: low = 1.0910
        ]

    def _bear_candles(self):
        # Bearish FVG: prev.low = 1.0910, next.high = 1.0900
        return [
            c(1.095, 1.096, 1.0910, 1.092),   # prev: low = 1.0910
            c(1.092, 1.093, 1.088, 1.089),    # displacement
            c(1.089, 1.0900, 1.087, 1.088),   # next: high = 1.0900
        ]

    def test_bullish_fvg_detected(self):
        cd = self._bull_candles()
        fvg = find_fvg(cd, displacement_idx=1, direction="bullish")
        assert fvg is not None
        assert fvg["bottom"] == pytest.approx(1.0900)
        assert fvg["top"] == pytest.approx(1.0910)
        assert fvg["midpoint"] == pytest.approx(1.0905)

    def test_bearish_fvg_detected(self):
        cd = self._bear_candles()
        fvg = find_fvg(cd, displacement_idx=1, direction="bearish")
        assert fvg is not None
        assert fvg["top"] == pytest.approx(1.0910)
        assert fvg["bottom"] == pytest.approx(1.0900)

    def test_no_fvg_when_no_gap(self):
        # prev.high = 1.0910, next.low = 1.0905 → overlap, no gap
        cd = [
            c(1.088, 1.0910, 1.088, 1.090),
            c(1.090, 1.095, 1.089, 1.094),
            c(1.094, 1.096, 1.0905, 1.095),   # next.low < prev.high
        ]
        assert find_fvg(cd, 1, "bullish") is None

    def test_returns_none_at_edge_missing_prev(self):
        cd = self._bull_candles()
        assert find_fvg(cd, displacement_idx=0, direction="bullish") is None

    def test_returns_none_at_edge_missing_next(self):
        cd = self._bull_candles()
        assert find_fvg(cd, displacement_idx=2, direction="bullish") is None

    def test_displacement_idx_stored_in_result(self):
        cd = self._bull_candles()
        fvg = find_fvg(cd, displacement_idx=1, direction="bullish")
        assert fvg["displacement_idx"] == 1


# ── check_fvg_retest ─────────────────────────────────────────────────────────

class TestCheckFVGRetest:
    def _bull_fvg(self):
        # FVG zone: bottom=1.0900, top=1.0910
        return {"top": 1.0910, "bottom": 1.0900, "midpoint": 1.0905}

    def _bear_fvg(self):
        return {"top": 1.0910, "bottom": 1.0900, "midpoint": 1.0905}

    def test_bullish_retest_detected(self):
        fvg = self._bull_fvg()
        # Bar dips into zone (low=1.0905 ≤ top=1.091) and closes inside (close=1.0908)
        candles = [c(1.093, 1.094, 1.0905, 1.0908)]
        idx = check_fvg_retest(candles, fvg, "bullish", from_idx=0)
        assert idx == 0

    def test_bullish_retest_touch_and_bounce(self):
        # Low just touches top of FVG, close above top → still a retest
        fvg = self._bull_fvg()
        candles = [c(1.094, 1.095, 1.0910, 1.093)]  # low = 1.091 = top → touches
        idx = check_fvg_retest(candles, fvg, "bullish", from_idx=0)
        assert idx == 0

    def test_bullish_invalidated_close_below_bottom(self):
        fvg = self._bull_fvg()
        candles = [c(1.092, 1.093, 1.0895, 1.0898)]  # close < 1.0900
        idx = check_fvg_retest(candles, fvg, "bullish", from_idx=0)
        assert idx is None

    def test_bullish_above_zone_no_retest(self):
        fvg = self._bull_fvg()
        # Price stays above FVG all the time
        candles = [c(1.095, 1.097, 1.093, 1.096)] * 5
        idx = check_fvg_retest(candles, fvg, "bullish", from_idx=0)
        assert idx is None

    def test_bearish_retest_detected(self):
        fvg = self._bear_fvg()
        # High enters zone from below (high=1.0905 ≥ bottom=1.090), close inside (close=1.0903)
        candles = [c(1.088, 1.0905, 1.087, 1.0903)]
        idx = check_fvg_retest(candles, fvg, "bearish", from_idx=0)
        assert idx == 0

    def test_bearish_invalidated_close_above_top(self):
        fvg = self._bear_fvg()
        candles = [c(1.088, 1.0920, 1.087, 1.0915)]  # close > 1.0910
        idx = check_fvg_retest(candles, fvg, "bearish", from_idx=0)
        assert idx is None

    def test_retest_found_after_wait(self):
        fvg = self._bull_fvg()
        # First 3 bars above zone, 4th bar retraces into zone
        above = c(1.095, 1.097, 1.093, 1.096)
        retest = c(1.093, 1.094, 1.0905, 1.0908)
        candles = [above, above, above, retest]
        idx = check_fvg_retest(candles, fvg, "bullish", from_idx=0)
        assert idx == 3

    def test_from_idx_respected(self):
        fvg = self._bull_fvg()
        retest = c(1.093, 1.094, 1.0905, 1.0908)
        candles = [retest, retest, retest]
        # from_idx=2 → only bar 2 checked
        idx = check_fvg_retest(candles, fvg, "bullish", from_idx=2)
        assert idx == 2

    def test_empty_candles_returns_none(self):
        fvg = self._bull_fvg()
        assert check_fvg_retest([], fvg, "bullish", 0) is None
