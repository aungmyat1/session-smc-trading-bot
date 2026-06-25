"""
Tests for SA-04: sweep_detector.py

10 required categories (per task spec):
  1.  Bullish sweep detected
  2.  Bearish sweep detected
  3.  Bullish close below range rejected       → close_outside_range
  4.  Bearish close above range rejected       → close_outside_range
  5.  Bullish bias mismatch                    → bias_mismatch
  6.  Bearish bias mismatch                    → bias_mismatch
  7.  Exact-touch low rejected                 → no_breach
  8.  Exact-touch high rejected                → no_breach
  9.  Floating-point precision edge case       → strict < / > still fires
  10. Malformed candle input                   → invalid_candle

Additional coverage:
  - sweep_price value correctness
  - close exactly at asian_low / asian_high → close_outside_range
  - neutral bias → bias_mismatch
  - both sides breached → bias picks the correct side
  - no movement in either direction → no_breach
"""

import unittest

from strategy.session_liquidity.sweep_detector import SweepResult, detect_sweep

# ─────────────────────────────────────────────────────────────────────────────
# Shared test levels
# ─────────────────────────────────────────────────────────────────────────────
ASIAN_HIGH = 1.0920
ASIAN_LOW  = 1.0880


def _candle(high: float, low: float, close: float, open_: float = None) -> dict:
    o = open_ if open_ is not None else (high + low) / 2
    return {"open": o, "high": high, "low": low, "close": close}


# ─────────────────────────────────────────────────────────────────────────────
# 1 — Bullish sweep detected
# ─────────────────────────────────────────────────────────────────────────────
class TestBullishSweepDetected(unittest.TestCase):

    def _valid(self) -> dict:
        # low=1.0875 < asian_low=1.0880; close=1.0895 > asian_low
        return _candle(high=1.0915, low=1.0875, close=1.0895)

    def test_detected_is_true(self):
        r = detect_sweep(self._valid(), ASIAN_HIGH, ASIAN_LOW, "bullish")
        self.assertTrue(r.detected)

    def test_side_is_long(self):
        r = detect_sweep(self._valid(), ASIAN_HIGH, ASIAN_LOW, "bullish")
        self.assertEqual(r.side, "long")

    def test_sweep_price_is_candle_low(self):
        r = detect_sweep(self._valid(), ASIAN_HIGH, ASIAN_LOW, "bullish")
        self.assertAlmostEqual(r.sweep_price, 1.0875, places=5)

    def test_reason_is_bullish_sweep(self):
        r = detect_sweep(self._valid(), ASIAN_HIGH, ASIAN_LOW, "bullish")
        self.assertEqual(r.reason, "bullish_sweep")


# ─────────────────────────────────────────────────────────────────────────────
# 2 — Bearish sweep detected
# ─────────────────────────────────────────────────────────────────────────────
class TestBearishSweepDetected(unittest.TestCase):

    def _valid(self) -> dict:
        # high=1.0925 > asian_high=1.0920; close=1.0905 < asian_high
        return _candle(high=1.0925, low=1.0885, close=1.0905)

    def test_detected_is_true(self):
        r = detect_sweep(self._valid(), ASIAN_HIGH, ASIAN_LOW, "bearish")
        self.assertTrue(r.detected)

    def test_side_is_short(self):
        r = detect_sweep(self._valid(), ASIAN_HIGH, ASIAN_LOW, "bearish")
        self.assertEqual(r.side, "short")

    def test_sweep_price_is_candle_high(self):
        r = detect_sweep(self._valid(), ASIAN_HIGH, ASIAN_LOW, "bearish")
        self.assertAlmostEqual(r.sweep_price, 1.0925, places=5)

    def test_reason_is_bearish_sweep(self):
        r = detect_sweep(self._valid(), ASIAN_HIGH, ASIAN_LOW, "bearish")
        self.assertEqual(r.reason, "bearish_sweep")


# ─────────────────────────────────────────────────────────────────────────────
# 3 — Bullish close below range rejected
# ─────────────────────────────────────────────────────────────────────────────
class TestBullishCloseOutsideRange(unittest.TestCase):

    def test_close_below_asian_low_rejected(self):
        # low=1.0875 < asian_low; close=1.0878 < asian_low → no snapback
        c = _candle(high=1.0915, low=1.0875, close=1.0878)
        r = detect_sweep(c, ASIAN_HIGH, ASIAN_LOW, "bullish")
        self.assertFalse(r.detected)
        self.assertEqual(r.reason, "close_outside_range")
        self.assertIsNone(r.side)
        self.assertIsNone(r.sweep_price)

    def test_close_exactly_at_asian_low_rejected(self):
        # close == asian_low: close <= asian_low is True → rejected
        c = _candle(high=1.0915, low=1.0875, close=1.0880)
        r = detect_sweep(c, ASIAN_HIGH, ASIAN_LOW, "bullish")
        self.assertFalse(r.detected)
        self.assertEqual(r.reason, "close_outside_range")

    def test_wick_below_close_far_below(self):
        # Candle breaks low significantly and close stays well below
        c = _candle(high=1.0910, low=1.0860, close=1.0865)
        r = detect_sweep(c, ASIAN_HIGH, ASIAN_LOW, "bullish")
        self.assertFalse(r.detected)
        self.assertEqual(r.reason, "close_outside_range")


# ─────────────────────────────────────────────────────────────────────────────
# 4 — Bearish close above range rejected
# ─────────────────────────────────────────────────────────────────────────────
class TestBearishCloseOutsideRange(unittest.TestCase):

    def test_close_above_asian_high_rejected(self):
        # high=1.0925 > asian_high; close=1.0922 > asian_high → no snapback
        c = _candle(high=1.0925, low=1.0885, close=1.0922)
        r = detect_sweep(c, ASIAN_HIGH, ASIAN_LOW, "bearish")
        self.assertFalse(r.detected)
        self.assertEqual(r.reason, "close_outside_range")
        self.assertIsNone(r.side)

    def test_close_exactly_at_asian_high_rejected(self):
        # close == asian_high: close >= asian_high is True → rejected
        c = _candle(high=1.0925, low=1.0885, close=1.0920)
        r = detect_sweep(c, ASIAN_HIGH, ASIAN_LOW, "bearish")
        self.assertFalse(r.detected)
        self.assertEqual(r.reason, "close_outside_range")

    def test_wick_above_close_far_above(self):
        c = _candle(high=1.0940, low=1.0890, close=1.0935)
        r = detect_sweep(c, ASIAN_HIGH, ASIAN_LOW, "bearish")
        self.assertFalse(r.detected)
        self.assertEqual(r.reason, "close_outside_range")


# ─────────────────────────────────────────────────────────────────────────────
# 5 — Bullish bias mismatch
#     bias="bullish" but candle sweeps the HIGH (bearish breach), not the LOW
# ─────────────────────────────────────────────────────────────────────────────
class TestBullishBiasMismatch(unittest.TestCase):

    def test_bearish_sweep_in_bullish_bias(self):
        # high=1.0925 > asian_high; low=1.0885 > asian_low (no low breach)
        # close=1.0910 < asian_high → valid bearish sweep pattern, wrong bias
        c = _candle(high=1.0925, low=1.0885, close=1.0910)
        r = detect_sweep(c, ASIAN_HIGH, ASIAN_LOW, "bullish")
        self.assertFalse(r.detected)
        self.assertEqual(r.reason, "bias_mismatch")
        self.assertIsNone(r.sweep_price)

    def test_bearish_sweep_close_inside_wrong_bias(self):
        # Same pattern, ensure the snapback doesn't rescue a mismatch
        c = _candle(high=1.0930, low=1.0890, close=1.0900)
        r = detect_sweep(c, ASIAN_HIGH, ASIAN_LOW, "bullish")
        self.assertFalse(r.detected)
        self.assertEqual(r.reason, "bias_mismatch")


# ─────────────────────────────────────────────────────────────────────────────
# 6 — Bearish bias mismatch
#     bias="bearish" but candle sweeps the LOW (bullish breach), not the HIGH
# ─────────────────────────────────────────────────────────────────────────────
class TestBearishBiasMismatch(unittest.TestCase):

    def test_bullish_sweep_in_bearish_bias(self):
        # low=1.0875 < asian_low; high=1.0915 < asian_high (no high breach)
        # close=1.0895 > asian_low → valid bullish sweep pattern, wrong bias
        c = _candle(high=1.0915, low=1.0875, close=1.0895)
        r = detect_sweep(c, ASIAN_HIGH, ASIAN_LOW, "bearish")
        self.assertFalse(r.detected)
        self.assertEqual(r.reason, "bias_mismatch")
        self.assertIsNone(r.sweep_price)

    def test_neutral_bias_is_also_mismatch(self):
        # A valid bullish sweep pattern with neutral bias → mismatch
        c = _candle(high=1.0915, low=1.0875, close=1.0895)
        r = detect_sweep(c, ASIAN_HIGH, ASIAN_LOW, "neutral")
        self.assertFalse(r.detected)
        self.assertEqual(r.reason, "bias_mismatch")


# ─────────────────────────────────────────────────────────────────────────────
# 7 — Exact-touch low rejected (strict inequality)
# ─────────────────────────────────────────────────────────────────────────────
class TestExactTouchLowRejected(unittest.TestCase):

    def test_low_exactly_equal_asian_low(self):
        # low == asian_low = 1.0880: strict < fails → no_breach
        c = _candle(high=1.0915, low=1.0880, close=1.0895)
        r = detect_sweep(c, ASIAN_HIGH, ASIAN_LOW, "bullish")
        self.assertFalse(r.detected)
        self.assertEqual(r.reason, "no_breach")

    def test_low_one_pip_above_asian_low(self):
        # low=1.0881 > asian_low → definitely no breach
        c = _candle(high=1.0915, low=1.0881, close=1.0895)
        r = detect_sweep(c, ASIAN_HIGH, ASIAN_LOW, "bullish")
        self.assertFalse(r.detected)
        self.assertEqual(r.reason, "no_breach")


# ─────────────────────────────────────────────────────────────────────────────
# 8 — Exact-touch high rejected (strict inequality)
# ─────────────────────────────────────────────────────────────────────────────
class TestExactTouchHighRejected(unittest.TestCase):

    def test_high_exactly_equal_asian_high(self):
        # high == asian_high = 1.0920: strict > fails → no_breach
        c = _candle(high=1.0920, low=1.0885, close=1.0905)
        r = detect_sweep(c, ASIAN_HIGH, ASIAN_LOW, "bearish")
        self.assertFalse(r.detected)
        self.assertEqual(r.reason, "no_breach")

    def test_high_one_pip_below_asian_high(self):
        # high=1.0919 < asian_high → no breach
        c = _candle(high=1.0919, low=1.0885, close=1.0905)
        r = detect_sweep(c, ASIAN_HIGH, ASIAN_LOW, "bearish")
        self.assertFalse(r.detected)
        self.assertEqual(r.reason, "no_breach")

    def test_candle_entirely_inside_range(self):
        # high=1.0910, low=1.0890 — no contact with either level
        c = _candle(high=1.0910, low=1.0890, close=1.0900)
        r = detect_sweep(c, ASIAN_HIGH, ASIAN_LOW, "bearish")
        self.assertFalse(r.detected)
        self.assertEqual(r.reason, "no_breach")


# ─────────────────────────────────────────────────────────────────────────────
# 9 — Floating-point precision edge case
# ─────────────────────────────────────────────────────────────────────────────
class TestFloatingPointPrecision(unittest.TestCase):

    def test_bullish_breach_by_one_subpip(self):
        """Breach of 0.00001 (1/10 pip) must be detected."""
        # asian_low=1.08800; low=1.08799 (breach by 0.00001)
        low = 1.08800 - 0.00001
        c = _candle(high=1.08900, low=low, close=1.08850)
        r = detect_sweep(c, ASIAN_HIGH, 1.08800, "bullish")
        self.assertTrue(r.detected)
        self.assertAlmostEqual(r.sweep_price, low, places=6)

    def test_bearish_breach_by_one_subpip(self):
        """Breach of 0.00001 above asian_high must be detected."""
        high = 1.09200 + 0.00001
        c = _candle(high=high, low=1.09100, close=1.09150)
        r = detect_sweep(c, 1.09200, ASIAN_LOW, "bearish")
        self.assertTrue(r.detected)
        self.assertAlmostEqual(r.sweep_price, high, places=6)

    def test_no_breach_by_one_subpip(self):
        """low=asian_low + 0.00001: strictly above → no breach."""
        low = 1.08800 + 0.00001
        c = _candle(high=1.08900, low=low, close=1.08850)
        r = detect_sweep(c, ASIAN_HIGH, 1.08800, "bullish")
        self.assertFalse(r.detected)
        self.assertEqual(r.reason, "no_breach")

    def test_close_above_asian_low_by_one_subpip_accepted(self):
        """close=asian_low + 0.00001: strictly above → snapback valid."""
        close = 1.08800 + 0.00001
        c = _candle(high=1.08900, low=1.08790, close=close)
        r = detect_sweep(c, ASIAN_HIGH, 1.08800, "bullish")
        self.assertTrue(r.detected)


# ─────────────────────────────────────────────────────────────────────────────
# 10 — Malformed candle input
# ─────────────────────────────────────────────────────────────────────────────
class TestMalformedCandleInput(unittest.TestCase):

    def _assert_invalid(self, candle):
        r = detect_sweep(candle, ASIAN_HIGH, ASIAN_LOW, "bullish")
        self.assertFalse(r.detected)
        self.assertEqual(r.reason, "invalid_candle")
        self.assertIsNone(r.side)
        self.assertIsNone(r.sweep_price)

    def test_missing_low_key(self):
        self._assert_invalid({"high": 1.0915, "close": 1.0895})

    def test_missing_high_key(self):
        self._assert_invalid({"low": 1.0875, "close": 1.0895})

    def test_missing_close_key(self):
        self._assert_invalid({"high": 1.0915, "low": 1.0875})

    def test_none_candle(self):
        # None is not subscriptable → TypeError
        r = detect_sweep(None, ASIAN_HIGH, ASIAN_LOW, "bullish")
        self.assertFalse(r.detected)
        self.assertEqual(r.reason, "invalid_candle")

    def test_low_is_none(self):
        self._assert_invalid({"high": 1.0915, "low": None, "close": 1.0895})

    def test_low_is_string(self):
        self._assert_invalid({"high": 1.0915, "low": "bad", "close": 1.0895})

    def test_empty_dict(self):
        self._assert_invalid({})


# ─────────────────────────────────────────────────────────────────────────────
# Additional: both sides breached
# ─────────────────────────────────────────────────────────────────────────────
class TestBothSidesBreached(unittest.TestCase):
    """Wide candle that wicks both Asian Low and Asian High."""

    def test_bullish_bias_picks_low_sweep(self):
        # low=1.0875 < asian_low AND high=1.0925 > asian_high; close=1.0905
        # bias="bullish" → check low breach first → bullish sweep
        c = _candle(high=1.0925, low=1.0875, close=1.0905)
        r = detect_sweep(c, ASIAN_HIGH, ASIAN_LOW, "bullish")
        self.assertTrue(r.detected)
        self.assertEqual(r.side, "long")
        self.assertAlmostEqual(r.sweep_price, 1.0875, places=5)

    def test_bearish_bias_picks_high_sweep(self):
        # Same wide candle, close=1.0895 < asian_high; bias="bearish"
        c = _candle(high=1.0925, low=1.0875, close=1.0895)
        r = detect_sweep(c, ASIAN_HIGH, ASIAN_LOW, "bearish")
        self.assertTrue(r.detected)
        self.assertEqual(r.side, "short")
        self.assertAlmostEqual(r.sweep_price, 1.0925, places=5)

    def test_bullish_bias_both_breached_close_below_range_rejected(self):
        # Wide candle, close still below asian_low → close_outside_range
        c = _candle(high=1.0925, low=1.0870, close=1.0878)
        r = detect_sweep(c, ASIAN_HIGH, ASIAN_LOW, "bullish")
        self.assertFalse(r.detected)
        self.assertEqual(r.reason, "close_outside_range")


# ─────────────────────────────────────────────────────────────────────────────
# Additional: SweepResult structure
# ─────────────────────────────────────────────────────────────────────────────
class TestSweepResultFields(unittest.TestCase):

    def test_non_detected_result_has_none_fields(self):
        c = _candle(high=1.0915, low=1.0885, close=1.0900)  # inside range
        r = detect_sweep(c, ASIAN_HIGH, ASIAN_LOW, "bullish")
        self.assertFalse(r.detected)
        self.assertIsNone(r.side)
        self.assertIsNone(r.sweep_price)
        self.assertIsInstance(r.reason, str)

    def test_detected_result_has_all_fields_populated(self):
        c = _candle(high=1.0915, low=1.0875, close=1.0895)
        r = detect_sweep(c, ASIAN_HIGH, ASIAN_LOW, "bullish")
        self.assertTrue(r.detected)
        self.assertIsNotNone(r.side)
        self.assertIsNotNone(r.sweep_price)
        self.assertIsNotNone(r.reason)

    def test_sweep_result_is_dataclass(self):
        from dataclasses import fields
        f_names = {f.name for f in fields(SweepResult)}
        self.assertEqual(f_names, {"detected", "side", "sweep_price", "reason"})


if __name__ == "__main__":
    unittest.main()
