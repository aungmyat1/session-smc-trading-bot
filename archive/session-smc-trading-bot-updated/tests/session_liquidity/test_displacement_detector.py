"""
Tests for SA-05: displacement_detector.py

Required categories (per TASK_QUEUE SA-05):
  1.  body > 1.2×ATR AND close in upper 25%   → bullish displacement
  2.  body > 1.2×ATR AND close in lower 25%   → bearish displacement
  3.  body just below threshold                → None / not detected
  4.  close in wrong quartile                  → not detected
  5.  NaN/None ATR (early bars)               → not detected
  6.  Wilder's seed at index 14 (not index 13)
  7.  body exactly at threshold               → not detected (strict >)
  8.  close exactly at 0.75 / 0.25 boundary   → not detected (strict >/<)
  9.  ATR correctness: constant-TR sequence    → constant ATR
  10. Malformed candle input                   → invalid_candle
  Additional:
  11. Zero ATR                                 → not detected
  12. Zero-range candle (high == low)          → not detected
  13. Unknown direction                        → not detected
  14. Wilder recursive update formula          → verified numerically
  15. DisplacementResult dataclass fields
"""

import unittest
from dataclasses import fields

from strategy.session_liquidity.displacement_detector import (
    DisplacementResult,
    detect_displacement,
    wilder_atr,
)

# ─────────────────────────────────────────────────────────────────────────────
# Shared test constants
# ─────────────────────────────────────────────────────────────────────────────

# Standard candle geometry used across most tests
#   high=1.0200, low=0.9900, range=0.0300
#   ATR=0.0100  → threshold=1.2×0.01=0.0120
_HIGH = 1.0200
_LOW = 0.9900
_RANGE = _HIGH - _LOW  # 0.0300
_ATR = 0.0100
_MULT = 1.2
_THR = _MULT * _ATR  # 0.0120


def _candle(high=_HIGH, low=_LOW, open_=None, close=None):
    """Build OHLC dict. open_ defaults to midpoint; close must be given or is mid."""
    mid = round((high + low) / 2, 6)
    return {
        "high": high,
        "low": low,
        "open": open_ if open_ is not None else mid,
        "close": close if close is not None else mid,
    }


def _at_close_pos(pos: float, high=_HIGH, low=_LOW) -> float:
    """Convert a fractional position [0..1] to a close price."""
    return round(low + pos * (high - low), 7)


# ─────────────────────────────────────────────────────────────────────────────
# Wilder ATR helpers
# ─────────────────────────────────────────────────────────────────────────────


def _constant_candles(n: int, range_size: float = 0.10, close: float = 1.0):
    """
    n candles with identical, non-gapping structure.
    TR[1..] = range_size for all (no gap from prev close since close == next open).
    """
    return [
        {"open": close, "high": close + range_size, "low": close, "close": close}
        for _ in range(n)
    ]


def _step_candles(
    n: int, base_range: float = 0.10, spike_range: float = 0.20, spike_at: int = 15
):
    """n candles where bar `spike_at` has a larger range."""
    candles = []
    for i in range(n):
        r = spike_range if i == spike_at else base_range
        candles.append(
            {
                "open": 1.0,
                "high": 1.0 + r,
                "low": 1.0,
                "close": 1.0,
            }
        )
    return candles


# ─────────────────────────────────────────────────────────────────────────────
# §A — wilder_atr tests
# ─────────────────────────────────────────────────────────────────────────────


class TestWilderATR(unittest.TestCase):

    # 6. Seed at index 14 (not 13)
    def test_atr_index_13_is_none(self):
        """With period=14, index 13 must be None — seed not yet computed."""
        candles = _constant_candles(20, range_size=0.10)
        atrs = wilder_atr(candles, period=14)
        self.assertIsNone(atrs[13])

    def test_atr_index_14_is_seed(self):
        """Index 14 is the first valid ATR (seed = mean of TR[1..14])."""
        candles = _constant_candles(20, range_size=0.10)
        atrs = wilder_atr(candles, period=14)
        self.assertIsNotNone(atrs[14])

    def test_atr_seed_value_constant_tr(self):
        """Seed = mean(TR[1..14]). With all TR=0.10, seed=0.10."""
        candles = _constant_candles(20, range_size=0.10)
        atrs = wilder_atr(candles, period=14)
        self.assertAlmostEqual(atrs[14], 0.10, places=10)

    # 9. ATR correctness: constant-TR sequence
    def test_constant_tr_gives_constant_atr(self):
        """If TR is constant, all ATR values from index 14 onward are equal."""
        candles = _constant_candles(30, range_size=0.10)
        atrs = wilder_atr(candles, period=14)
        for i in range(14, 30):
            self.assertAlmostEqual(
                atrs[i], 0.10, places=10, msg=f"ATR[{i}] should be 0.10"
            )

    def test_indices_0_to_13_all_none(self):
        """All entries before seed are None."""
        candles = _constant_candles(20)
        atrs = wilder_atr(candles, period=14)
        for i in range(14):
            self.assertIsNone(atrs[i], msg=f"ATR[{i}] should be None")

    def test_empty_candles(self):
        """Empty input returns empty list."""
        self.assertEqual(wilder_atr([], period=14), [])

    def test_exactly_period_candles_all_none(self):
        """If len == period, seed cannot be formed (need period+1 candles)."""
        candles = _constant_candles(14)
        atrs = wilder_atr(candles, period=14)
        self.assertTrue(all(a is None for a in atrs))

    def test_exactly_period_plus_one_candles_has_seed(self):
        """15 candles (period=14): only ATR[14] is non-None."""
        candles = _constant_candles(15)
        atrs = wilder_atr(candles, period=14)
        for i in range(14):
            self.assertIsNone(atrs[i])
        self.assertIsNotNone(atrs[14])

    def test_output_length_equals_input_length(self):
        """Result list always has the same length as input."""
        for n in [0, 5, 14, 15, 30]:
            self.assertEqual(len(wilder_atr(_constant_candles(n))), n)

    # 14. Wilder recursive update formula
    def test_recursive_update_after_spike(self):
        """
        After the seed, one large TR bar should push ATR up by a predictable amount.

        Setup: 16 constant-TR bars then one spike at index 15.
          seed (index 14) = 0.10
          TR[15] = 0.20
          ATR[15] = (0.10 × 13 + 0.20) / 14 = (1.30 + 0.20) / 14 = 1.50/14 ≈ 0.107143
        """
        candles = _step_candles(n=16, base_range=0.10, spike_range=0.20, spike_at=15)
        atrs = wilder_atr(candles, period=14)
        expected = (0.10 * 13 + 0.20) / 14
        self.assertAlmostEqual(atrs[15], expected, places=8)

    def test_atr_decreases_with_small_tr(self):
        """After large bars, introducing small TR bars pulls ATR down over time."""
        # 14 bars with TR=0.20, then bars with TR=0.01
        candles = _constant_candles(14, range_size=0.20)  # warm-up
        # Add enough small bars for ATR to clearly decrease
        for _ in range(50):
            candles.append({"open": 1.0, "high": 1.001, "low": 1.0, "close": 1.0})
        atrs = wilder_atr(candles, period=14)
        # ATR[14] = 0.20 (all large), ATR[-1] should be much smaller
        self.assertGreater(atrs[14], atrs[-1])


# ─────────────────────────────────────────────────────────────────────────────
# §B — detect_displacement tests
# ─────────────────────────────────────────────────────────────────────────────


class TestBullishDisplacement(unittest.TestCase):
    """Category 1 — bullish displacement detected."""

    def _bullish_candle(self):
        # body=0.0190 > threshold=0.0120; close_pos=0.9667 > 0.75
        return _candle(open_=1.0000, close=1.0190)

    def test_detected_true(self):
        r = detect_displacement(self._bullish_candle(), _ATR, "long")
        self.assertTrue(r.detected)

    def test_side_is_long(self):
        r = detect_displacement(self._bullish_candle(), _ATR, "long")
        self.assertEqual(r.side, "long")

    def test_reason_is_bullish_displacement(self):
        r = detect_displacement(self._bullish_candle(), _ATR, "long")
        self.assertEqual(r.reason, "bullish_displacement")

    def test_body_size_recorded(self):
        r = detect_displacement(self._bullish_candle(), _ATR, "long")
        self.assertAlmostEqual(r.body_size, 0.0190, places=5)

    def test_close_position_recorded(self):
        r = detect_displacement(self._bullish_candle(), _ATR, "long")
        expected_pos = (1.0190 - _LOW) / _RANGE  # (1.0190-0.9900)/0.0300 = 0.9667
        self.assertAlmostEqual(r.close_position, expected_pos, places=4)

    def test_atr_recorded(self):
        r = detect_displacement(self._bullish_candle(), _ATR, "long")
        self.assertEqual(r.atr, _ATR)


class TestBearishDisplacement(unittest.TestCase):
    """Category 2 — bearish displacement detected."""

    def _bearish_candle(self):
        # body=0.0290 > threshold=0.0120; close_pos=0.0333 < 0.25
        return _candle(open_=1.0200, close=0.9910)

    def test_detected_true(self):
        r = detect_displacement(self._bearish_candle(), _ATR, "short")
        self.assertTrue(r.detected)

    def test_side_is_short(self):
        r = detect_displacement(self._bearish_candle(), _ATR, "short")
        self.assertEqual(r.side, "short")

    def test_reason_is_bearish_displacement(self):
        r = detect_displacement(self._bearish_candle(), _ATR, "short")
        self.assertEqual(r.reason, "bearish_displacement")

    def test_body_and_position(self):
        r = detect_displacement(self._bearish_candle(), _ATR, "short")
        self.assertAlmostEqual(r.body_size, 0.0290, places=5)
        expected_pos = (0.9910 - _LOW) / _RANGE  # 0.0333
        self.assertAlmostEqual(r.close_position, expected_pos, places=4)


class TestBodyGate(unittest.TestCase):
    """Category 3 & 7 — body threshold (strict >)."""

    def test_body_exactly_at_threshold_rejected(self):
        # body = 0.0120 = threshold → body <= threshold → rejected
        c = _candle(open_=1.0000, close=_at_close_pos(0.90))  # high close_pos
        # Adjust body to exactly _THR = 0.0120
        c["close"] = round(c["open"] + _THR, 6)
        r = detect_displacement(c, _ATR, "long")
        self.assertFalse(r.detected)
        self.assertIn("≤", r.reason)

    def test_body_just_below_threshold_rejected(self):
        # body = 0.0119 < 0.0120 → rejected
        c = _candle(open_=1.0000, close=round(1.0000 + _THR - 0.0001, 6))
        r = detect_displacement(c, _ATR, "long")
        self.assertFalse(r.detected)

    def test_body_one_subpip_above_threshold_accepted(self):
        # body = 0.01201 > 0.0120 → body gate passes (may still fail quartile)
        c = _candle(open_=1.0000, close=round(1.0000 + _THR + 0.00001, 7))
        c["high"] = max(c["high"], c["close"] + 0.0001)
        # Now force close_pos > 0.75
        close_target = _at_close_pos(0.90)
        c["close"] = close_target
        c["open"] = round(close_target - _THR - 0.00001, 7)
        r = detect_displacement(c, _ATR, "long")
        # body just above threshold; close at 0.90 > 0.75 → detected
        self.assertTrue(r.detected)

    def test_body_and_close_position_none_when_body_fails(self):
        """close_position must be None when body gate fails (not yet computed)."""
        c = _candle(open_=1.0000, close=1.0000 + _THR - 0.0001)
        r = detect_displacement(c, _ATR, "long")
        self.assertFalse(r.detected)
        self.assertIsNone(r.close_position)


class TestQuartileGate(unittest.TestCase):
    """Category 4 & 8 — quartile boundaries (strict > / <)."""

    def test_bullish_close_exactly_at_75_pct_rejected(self):
        """close_pos = 0.75 exactly → not > 0.75 → rejected."""
        close = _at_close_pos(0.75)
        # Ensure body > threshold
        open_ = round(close - _THR - 0.0001, 7)
        c = _candle(open_=open_, close=close)
        r = detect_displacement(c, _ATR, "long")
        self.assertFalse(r.detected)
        self.assertAlmostEqual(r.close_position, 0.75, places=4)

    def test_bullish_close_just_above_75_pct_detected(self):
        """close_pos = 0.76 → > 0.75 → passes quartile gate."""
        close = _at_close_pos(0.76)
        open_ = round(close - _THR - 0.0001, 7)
        c = _candle(open_=open_, close=close)
        r = detect_displacement(c, _ATR, "long")
        self.assertTrue(r.detected)

    def test_bearish_close_exactly_at_25_pct_rejected(self):
        """close_pos = 0.25 exactly → not < 0.25 → rejected."""
        close = _at_close_pos(0.25)
        open_ = round(close + _THR + 0.0001, 7)
        c = _candle(open_=open_, close=close)
        r = detect_displacement(c, _ATR, "short")
        self.assertFalse(r.detected)
        self.assertAlmostEqual(r.close_position, 0.25, places=4)

    def test_bearish_close_just_below_25_pct_detected(self):
        """close_pos = 0.24 → < 0.25 → passes quartile gate."""
        close = _at_close_pos(0.24)
        open_ = round(close + _THR + 0.0001, 7)
        c = _candle(open_=open_, close=close)
        r = detect_displacement(c, _ATR, "short")
        self.assertTrue(r.detected)

    def test_bullish_body_ok_but_close_in_lower_half_rejected(self):
        """Direction=long, body passes, but close in lower 25% — rejected."""
        close = _at_close_pos(0.10)  # close near low
        open_ = round(
            close - _THR - 0.0001, 7
        )  # bearish body for this close (open > close?)
        # Actually for close < open (bearish candle), direction=long means wrong quartile
        # close_pos=0.10 < 0.75 → rejected
        open_ = round(close + _THR + 0.0001, 7)  # open above close, body > threshold
        c = _candle(open_=open_, close=close)
        r = detect_displacement(c, _ATR, "long")
        self.assertFalse(r.detected)
        self.assertIn("75%", r.reason)

    def test_bearish_body_ok_but_close_in_upper_half_rejected(self):
        """Direction=short, body passes, but close in upper 75% — rejected."""
        close = _at_close_pos(0.90)
        open_ = round(close - _THR - 0.0001, 7)  # open below close, body > threshold
        c = _candle(open_=open_, close=close)
        r = detect_displacement(c, _ATR, "short")
        self.assertFalse(r.detected)
        self.assertIn("25%", r.reason)


class TestATRAvailability(unittest.TestCase):
    """Category 5 — ATR unavailable."""

    def test_none_atr_returns_not_detected(self):
        c = _candle(open_=1.0000, close=1.0190)
        r = detect_displacement(c, None, "long")
        self.assertFalse(r.detected)
        self.assertEqual(r.reason, "atr_unavailable")
        self.assertIsNone(r.atr)

    def test_none_atr_body_size_still_computed(self):
        """Even when ATR is None, body_size should be computed for logging."""
        c = _candle(open_=1.0000, close=1.0190)
        r = detect_displacement(c, None, "long")
        self.assertAlmostEqual(r.body_size, 0.0190, places=5)

    # 11. Zero ATR
    def test_zero_atr_returns_not_detected(self):
        c = _candle(open_=1.0000, close=1.0190)
        r = detect_displacement(c, 0.0, "long")
        self.assertFalse(r.detected)
        self.assertEqual(r.reason, "atr_zero")

    def test_negative_atr_returns_not_detected(self):
        c = _candle(open_=1.0000, close=1.0190)
        r = detect_displacement(c, -0.001, "long")
        self.assertFalse(r.detected)
        self.assertEqual(r.reason, "atr_zero")


class TestMalformedCandle(unittest.TestCase):
    """Category 10 — malformed candle input."""

    def _assert_invalid(self, candle):
        r = detect_displacement(candle, _ATR, "long")
        self.assertFalse(r.detected)
        self.assertEqual(r.reason, "invalid_candle")

    def test_none_candle(self):
        r = detect_displacement(None, _ATR, "long")
        self.assertFalse(r.detected)
        self.assertEqual(r.reason, "invalid_candle")

    def test_missing_close(self):
        self._assert_invalid({"high": 1.02, "low": 0.99, "open": 1.00})

    def test_missing_open(self):
        self._assert_invalid({"high": 1.02, "low": 0.99, "close": 1.01})

    def test_none_value(self):
        self._assert_invalid({"high": 1.02, "low": None, "open": 1.00, "close": 1.01})

    def test_string_value(self):
        self._assert_invalid({"high": "abc", "low": 0.99, "open": 1.00, "close": 1.01})

    def test_empty_dict(self):
        self._assert_invalid({})


class TestZeroRangeCandle(unittest.TestCase):
    """Category 12 — zero-range (doji) candle."""

    def test_high_equals_low_rejected(self):
        # high == low: range == 0, cannot compute close_position
        c = {"high": 1.05, "low": 1.05, "open": 1.05, "close": 1.05}
        r = detect_displacement(c, _ATR, "long")
        self.assertFalse(r.detected)
        self.assertEqual(r.reason, "zero_range_candle")

    def test_high_equals_low_body_still_zero(self):
        c = {"high": 1.05, "low": 1.05, "open": 1.05, "close": 1.05}
        r = detect_displacement(c, _ATR, "long")
        self.assertAlmostEqual(r.body_size, 0.0, places=6)


class TestUnknownDirection(unittest.TestCase):
    """Category 13 — invalid direction string."""

    def test_unknown_direction_not_detected(self):
        # Body passes, quartile check skipped for unknown direction
        c = _candle(open_=1.0000, close=1.0190)
        r = detect_displacement(c, _ATR, "sideways")
        self.assertFalse(r.detected)
        self.assertIn("unknown_direction", r.reason)


class TestDisplacementResultDataclass(unittest.TestCase):
    """Category 15 — dataclass structure."""

    def test_field_names(self):
        expected = {"detected", "side", "body_size", "atr", "close_position", "reason"}
        actual = {f.name for f in fields(DisplacementResult)}
        self.assertEqual(actual, expected)

    def test_not_detected_result_has_none_side(self):
        c = _candle(open_=1.0000, close=1.0110)  # body=0.011 < threshold=0.012
        r = detect_displacement(c, _ATR, "long")
        self.assertFalse(r.detected)
        self.assertIsNone(r.side)

    def test_detected_result_all_fields_populated(self):
        c = _candle(open_=1.0000, close=1.0190)
        r = detect_displacement(c, _ATR, "long")
        self.assertTrue(r.detected)
        self.assertIsNotNone(r.side)
        self.assertIsNotNone(r.close_position)
        self.assertIsNotNone(r.atr)
        self.assertIsInstance(r.reason, str)


class TestIntegrationWithATR(unittest.TestCase):
    """Integration: wilder_atr output fed directly to detect_displacement."""

    def test_early_bars_atr_none_rejected(self):
        """Bars 0-13 have None ATR → all displacement calls return not-detected."""
        candles = _constant_candles(20)
        atrs = wilder_atr(candles, period=14)
        for i in range(14):
            candle = {"open": 1.0, "high": 1.05, "low": 0.95, "close": 1.04}
            r = detect_displacement(candle, atrs[i], "long")
            self.assertFalse(
                r.detected, msg=f"bar {i} should be not-detected (ATR=None)"
            )

    def test_bar_14_atr_available(self):
        """ATR at index 14 is valid, displacement can be detected."""
        candles = _constant_candles(20, range_size=0.01)
        atrs = wilder_atr(candles, period=14)
        self.assertIsNotNone(atrs[14])
        # Any candle with sufficient body can now be detected
        big_body = {"open": 1.0000, "high": 1.0200, "low": 0.9900, "close": 1.0195}
        r = detect_displacement(big_body, atrs[14], "long")
        # body = 0.0195, threshold = 1.2 × 0.01 = 0.012 → body passes
        # close_pos ≈ 0.9833 > 0.75 → detected
        self.assertTrue(r.detected)


if __name__ == "__main__":
    unittest.main()
