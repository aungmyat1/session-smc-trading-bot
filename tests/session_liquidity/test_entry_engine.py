"""
Tests for SA-06: entry_engine.py

Required categories (per SA-06 task spec):
  1.  Valid long signal
  2.  Valid short signal
  3.  Invalid sweep (detected=False)
  4.  Invalid displacement (detected=False)
  5.  Invalid session
  6.  Invalid RR (rr <= 0)
  7.  Invalid risk (degenerate geometry → risk <= 0)
  8.  Invalid asian range (high <= low or None)
  9.  SL buffer applied correctly
  10. TP calculation
  Additional:
  11. Signal dataclass field names match execution contract
  12. Timestamp from candle 'time' string
  13. Timestamp from candle 'time' datetime object
  14. Missing candle 'close' key
  15. Sweep detected but sweep_price=None (defensive guard)
  16. Negative sl_buffer_pips
  17. Both-zero buffer (0-pip buffer)
  18. Long: risk computed as entry - stop_loss
  19. Short: risk computed as stop_loss - entry
  20. reason string contains side, sweep_price, entry, RR
"""

import unittest
from dataclasses import fields
from datetime import date, datetime, timezone

from strategy.session_liquidity.entry_engine import Signal, build_signal
from strategy.session_liquidity.session_builder import AsianRange
from strategy.session_liquidity.sweep_detector import SweepResult
from strategy.session_liquidity.displacement_detector import DisplacementResult

_UTC = timezone.utc

# ─────────────────────────────────────────────────────────────────────────────
# Shared test fixtures
# ─────────────────────────────────────────────────────────────────────────────

# Asian range: 1.0700 → 1.0800 (100 pip range)
_ASIAN = AsianRange(trade_date=date(2024, 1, 15), high=1.0800, low=1.0700)

# Valid long: sweep pierced below 1.0700, closed back inside
_SWEEP_LONG = SweepResult(
    detected=True,
    side="long",
    sweep_price=1.0682,  # wick low that pierced below asian_low
    reason="bullish_sweep",
)

# Valid short: sweep pierced above 1.0800, closed back inside
_SWEEP_SHORT = SweepResult(
    detected=True,
    side="short",
    sweep_price=1.0818,  # wick high that pierced above asian_high
    reason="bearish_sweep",
)

_DISP_LONG = DisplacementResult(
    detected=True,
    side="long",
    body_size=0.0015,
    atr=0.0010,
    close_position=0.92,
    reason="bullish_displacement",
)

_DISP_SHORT = DisplacementResult(
    detected=True,
    side="short",
    body_size=0.0015,
    atr=0.0010,
    close_position=0.08,
    reason="bearish_displacement",
)

_DISP_NONE = DisplacementResult(
    detected=False,
    side=None,
    body_size=0.0008,
    atr=0.0010,
    close_position=None,
    reason="body(0.00080) ≤ 1.2×ATR(0.00120)",
)

_CANDLE_LONG = {
    "time": "2024-01-15T07:45:00Z",
    "open": 1.0715,
    "high": 1.0755,
    "low": 1.0710,
    "close": 1.0750,  # entry for long
}

_CANDLE_SHORT = {
    "time": "2024-01-15T08:00:00Z",
    "open": 1.0790,
    "high": 1.0795,
    "low": 1.0755,
    "close": 1.0760,  # entry for short
}

_RR = 3.0
_BUF = 2.0  # pips


# ─────────────────────────────────────────────────────────────────────────────
# Category 1 — Valid long signal
# ─────────────────────────────────────────────────────────────────────────────


class TestValidLongSignal(unittest.TestCase):

    def setUp(self):
        self.sig = build_signal(
            _CANDLE_LONG,
            _SWEEP_LONG,
            _DISP_LONG,
            _ASIAN,
            "london",
            _RR,
            _BUF,
        )

    def test_returns_signal(self):
        self.assertIsNotNone(self.sig)
        self.assertIsInstance(self.sig, Signal)

    def test_side_long(self):
        self.assertEqual(self.sig.side, "long")

    def test_entry_is_close(self):
        self.assertAlmostEqual(self.sig.entry, 1.0750, places=5)

    def test_stop_loss_below_sweep(self):
        expected_sl = _SWEEP_LONG.sweep_price - _BUF * 0.0001
        self.assertAlmostEqual(self.sig.stop_loss, expected_sl, places=5)

    def test_risk_positive(self):
        self.assertGreater(self.sig.risk_pips, 0)

    def test_risk_equals_entry_minus_sl(self):
        expected_risk_pips = (self.sig.entry - self.sig.stop_loss) / 0.0001
        self.assertAlmostEqual(self.sig.risk_pips, expected_risk_pips, places=4)

    def test_tp_above_entry(self):
        self.assertGreater(self.sig.take_profit, self.sig.entry)

    def test_session_london(self):
        self.assertEqual(self.sig.session, "london")

    def test_rr_stored(self):
        self.assertEqual(self.sig.rr, _RR)


# ─────────────────────────────────────────────────────────────────────────────
# Category 2 — Valid short signal
# ─────────────────────────────────────────────────────────────────────────────


class TestValidShortSignal(unittest.TestCase):

    def setUp(self):
        self.sig = build_signal(
            _CANDLE_SHORT,
            _SWEEP_SHORT,
            _DISP_SHORT,
            _ASIAN,
            "new_york",
            _RR,
            _BUF,
        )

    def test_returns_signal(self):
        self.assertIsNotNone(self.sig)

    def test_side_short(self):
        self.assertEqual(self.sig.side, "short")

    def test_entry_is_close(self):
        self.assertAlmostEqual(self.sig.entry, 1.0760, places=5)

    def test_stop_loss_above_sweep(self):
        expected_sl = _SWEEP_SHORT.sweep_price + _BUF * 0.0001
        self.assertAlmostEqual(self.sig.stop_loss, expected_sl, places=5)

    def test_tp_below_entry(self):
        self.assertLess(self.sig.take_profit, self.sig.entry)

    def test_session_new_york(self):
        self.assertEqual(self.sig.session, "new_york")

    def test_risk_equals_sl_minus_entry(self):
        expected_risk_pips = (self.sig.stop_loss - self.sig.entry) / 0.0001
        self.assertAlmostEqual(self.sig.risk_pips, expected_risk_pips, places=4)


# ─────────────────────────────────────────────────────────────────────────────
# Category 3 — Invalid sweep
# ─────────────────────────────────────────────────────────────────────────────


class TestInvalidSweep(unittest.TestCase):

    def _sweep_none_detected(self):
        return SweepResult(
            detected=False, side=None, sweep_price=None, reason="no_breach"
        )

    def test_sweep_not_detected_returns_none(self):
        self.assertIsNone(
            build_signal(
                _CANDLE_LONG,
                self._sweep_none_detected(),
                _DISP_LONG,
                _ASIAN,
                "london",
                _RR,
                _BUF,
            )
        )

    def test_none_sweep_returns_none(self):
        self.assertIsNone(
            build_signal(
                _CANDLE_LONG,
                None,
                _DISP_LONG,
                _ASIAN,
                "london",
                _RR,
                _BUF,
            )
        )

    def test_bias_mismatch_sweep_returns_none(self):
        s = SweepResult(
            detected=False, side=None, sweep_price=None, reason="bias_mismatch"
        )
        self.assertIsNone(
            build_signal(
                _CANDLE_LONG,
                s,
                _DISP_LONG,
                _ASIAN,
                "london",
                _RR,
                _BUF,
            )
        )


# ─────────────────────────────────────────────────────────────────────────────
# Category 4 — Invalid displacement
# ─────────────────────────────────────────────────────────────────────────────


class TestInvalidDisplacement(unittest.TestCase):

    def test_displacement_not_detected_returns_none(self):
        self.assertIsNone(
            build_signal(
                _CANDLE_LONG,
                _SWEEP_LONG,
                _DISP_NONE,
                _ASIAN,
                "london",
                _RR,
                _BUF,
            )
        )

    def test_none_displacement_returns_none(self):
        self.assertIsNone(
            build_signal(
                _CANDLE_LONG,
                _SWEEP_LONG,
                None,
                _ASIAN,
                "london",
                _RR,
                _BUF,
            )
        )

    def test_atr_unavailable_displacement_returns_none(self):
        d = DisplacementResult(
            detected=False,
            side=None,
            body_size=0.002,
            atr=None,
            close_position=None,
            reason="atr_unavailable",
        )
        self.assertIsNone(
            build_signal(
                _CANDLE_LONG,
                _SWEEP_LONG,
                d,
                _ASIAN,
                "london",
                _RR,
                _BUF,
            )
        )


# ─────────────────────────────────────────────────────────────────────────────
# Category 5 — Invalid session
# ─────────────────────────────────────────────────────────────────────────────


class TestInvalidSession(unittest.TestCase):

    def _call(self, session):
        return build_signal(
            _CANDLE_LONG,
            _SWEEP_LONG,
            _DISP_LONG,
            _ASIAN,
            session,
            _RR,
            _BUF,
        )

    def test_asian_session_rejected(self):
        self.assertIsNone(self._call("asian"))

    def test_none_session_rejected(self):
        self.assertIsNone(self._call(None))

    def test_empty_string_rejected(self):
        self.assertIsNone(self._call(""))

    def test_random_string_rejected(self):
        self.assertIsNone(self._call("tokyo"))

    def test_london_accepted(self):
        self.assertIsNotNone(self._call("london"))

    def test_new_york_accepted(self):
        self.assertIsNotNone(self._call("new_york"))


# ─────────────────────────────────────────────────────────────────────────────
# Category 6 — Invalid RR
# ─────────────────────────────────────────────────────────────────────────────


class TestInvalidRR(unittest.TestCase):

    def test_rr_zero_rejected(self):
        self.assertIsNone(
            build_signal(
                _CANDLE_LONG,
                _SWEEP_LONG,
                _DISP_LONG,
                _ASIAN,
                "london",
                0.0,
                _BUF,
            )
        )

    def test_rr_negative_rejected(self):
        self.assertIsNone(
            build_signal(
                _CANDLE_LONG,
                _SWEEP_LONG,
                _DISP_LONG,
                _ASIAN,
                "london",
                -1.0,
                _BUF,
            )
        )

    def test_rr_fractional_accepted(self):
        sig = build_signal(
            _CANDLE_LONG,
            _SWEEP_LONG,
            _DISP_LONG,
            _ASIAN,
            "london",
            1.5,
            _BUF,
        )
        self.assertIsNotNone(sig)
        self.assertEqual(sig.rr, 1.5)


# ─────────────────────────────────────────────────────────────────────────────
# Category 7 — Invalid risk (degenerate geometry)
# ─────────────────────────────────────────────────────────────────────────────


class TestInvalidRisk(unittest.TestCase):

    def test_long_entry_below_sl_rejected(self):
        # entry 1.0680 < sl = 1.0682 - 0.0002 = 1.0680 → risk = 1.0680 - 1.0680 = 0
        candle = {**_CANDLE_LONG, "close": 1.0680}
        sweep = SweepResult(
            detected=True, side="long", sweep_price=1.0682, reason="bullish_sweep"
        )
        self.assertIsNone(
            build_signal(candle, sweep, _DISP_LONG, _ASIAN, "london", _RR, _BUF)
        )

    def test_short_entry_above_sl_rejected(self):
        # entry 1.0822 > sl = 1.0818 + 0.0002 = 1.0820 → risk = 1.0820 - 1.0822 < 0
        candle = {**_CANDLE_SHORT, "close": 1.0822}
        sweep = SweepResult(
            detected=True, side="short", sweep_price=1.0818, reason="bearish_sweep"
        )
        self.assertIsNone(
            build_signal(candle, sweep, _DISP_SHORT, _ASIAN, "london", _RR, _BUF)
        )

    def test_long_entry_exactly_at_sl_rejected(self):
        # entry exactly at sl → risk = 0
        buf = 2.0
        sweep_price = 1.0682
        sl = sweep_price - buf * 0.0001
        candle = {**_CANDLE_LONG, "close": sl}
        sweep = SweepResult(
            detected=True, side="long", sweep_price=sweep_price, reason="bullish_sweep"
        )
        self.assertIsNone(
            build_signal(candle, sweep, _DISP_LONG, _ASIAN, "london", _RR, buf)
        )


# ─────────────────────────────────────────────────────────────────────────────
# Category 8 — Invalid asian range
# ─────────────────────────────────────────────────────────────────────────────


class TestInvalidAsianRange(unittest.TestCase):

    def test_none_asian_range_rejected(self):
        self.assertIsNone(
            build_signal(
                _CANDLE_LONG,
                _SWEEP_LONG,
                _DISP_LONG,
                None,
                "london",
                _RR,
                _BUF,
            )
        )

    def test_high_equals_low_rejected(self):
        flat = AsianRange(trade_date=date(2024, 1, 15), high=1.0750, low=1.0750)
        self.assertIsNone(
            build_signal(
                _CANDLE_LONG,
                _SWEEP_LONG,
                _DISP_LONG,
                flat,
                "london",
                _RR,
                _BUF,
            )
        )

    def test_high_below_low_rejected(self):
        inverted = AsianRange(trade_date=date(2024, 1, 15), high=1.0700, low=1.0800)
        self.assertIsNone(
            build_signal(
                _CANDLE_LONG,
                _SWEEP_LONG,
                _DISP_LONG,
                inverted,
                "london",
                _RR,
                _BUF,
            )
        )

    def test_valid_asian_range_accepted(self):
        self.assertIsNotNone(
            build_signal(
                _CANDLE_LONG,
                _SWEEP_LONG,
                _DISP_LONG,
                _ASIAN,
                "london",
                _RR,
                _BUF,
            )
        )


# ─────────────────────────────────────────────────────────────────────────────
# Category 9 — SL buffer applied correctly
# ─────────────────────────────────────────────────────────────────────────────


class TestSLBuffer(unittest.TestCase):

    def test_long_sl_is_sweep_minus_buffer(self):
        buf = 3.0
        sig = build_signal(
            _CANDLE_LONG, _SWEEP_LONG, _DISP_LONG, _ASIAN, "london", _RR, buf
        )
        self.assertIsNotNone(sig)
        expected = _SWEEP_LONG.sweep_price - buf * 0.0001
        self.assertAlmostEqual(sig.stop_loss, expected, places=6)

    def test_short_sl_is_sweep_plus_buffer(self):
        buf = 3.0
        sig = build_signal(
            _CANDLE_SHORT, _SWEEP_SHORT, _DISP_SHORT, _ASIAN, "london", _RR, buf
        )
        self.assertIsNotNone(sig)
        expected = _SWEEP_SHORT.sweep_price + buf * 0.0001
        self.assertAlmostEqual(sig.stop_loss, expected, places=6)

    def test_zero_buffer_accepted(self):
        sig = build_signal(
            _CANDLE_LONG, _SWEEP_LONG, _DISP_LONG, _ASIAN, "london", _RR, 0.0
        )
        self.assertIsNotNone(sig)
        self.assertAlmostEqual(sig.stop_loss, _SWEEP_LONG.sweep_price, places=6)

    def test_negative_buffer_rejected(self):
        self.assertIsNone(
            build_signal(
                _CANDLE_LONG,
                _SWEEP_LONG,
                _DISP_LONG,
                _ASIAN,
                "london",
                _RR,
                -1.0,
            )
        )


# ─────────────────────────────────────────────────────────────────────────────
# Category 10 — TP calculation
# ─────────────────────────────────────────────────────────────────────────────


class TestTPCalculation(unittest.TestCase):

    def test_long_tp_equals_entry_plus_risk_times_rr(self):
        sig = build_signal(
            _CANDLE_LONG, _SWEEP_LONG, _DISP_LONG, _ASIAN, "london", _RR, _BUF
        )
        sl_dist = sig.entry - sig.stop_loss
        expected_tp = sig.entry + sl_dist * _RR
        self.assertAlmostEqual(sig.take_profit, expected_tp, places=6)

    def test_short_tp_equals_entry_minus_risk_times_rr(self):
        sig = build_signal(
            _CANDLE_SHORT, _SWEEP_SHORT, _DISP_SHORT, _ASIAN, "new_york", _RR, _BUF
        )
        sl_dist = sig.stop_loss - sig.entry
        expected_tp = sig.entry - sl_dist * _RR
        self.assertAlmostEqual(sig.take_profit, expected_tp, places=6)

    def test_reward_pips_equals_risk_pips_times_rr(self):
        sig = build_signal(
            _CANDLE_LONG, _SWEEP_LONG, _DISP_LONG, _ASIAN, "london", _RR, _BUF
        )
        self.assertAlmostEqual(sig.reward_pips, sig.risk_pips * _RR, places=4)

    def test_rr2_tp(self):
        sig = build_signal(
            _CANDLE_LONG, _SWEEP_LONG, _DISP_LONG, _ASIAN, "london", 2.0, _BUF
        )
        sl_dist = sig.entry - sig.stop_loss
        self.assertAlmostEqual(sig.take_profit, sig.entry + sl_dist * 2.0, places=6)

    def test_rr5_tp(self):
        sig = build_signal(
            _CANDLE_LONG, _SWEEP_LONG, _DISP_LONG, _ASIAN, "london", 5.0, _BUF
        )
        sl_dist = sig.entry - sig.stop_loss
        self.assertAlmostEqual(sig.take_profit, sig.entry + sl_dist * 5.0, places=6)


# ─────────────────────────────────────────────────────────────────────────────
# Category 11 — Signal dataclass fields match execution contract
# ─────────────────────────────────────────────────────────────────────────────


class TestSignalDataclass(unittest.TestCase):

    def test_all_required_fields_present(self):
        expected = {
            "side",
            "entry",
            "stop_loss",
            "take_profit",
            "risk_pips",
            "reward_pips",
            "rr",
            "session",
            "timestamp",
            "reason",
        }
        actual = {f.name for f in fields(Signal)}
        self.assertEqual(actual, expected)

    def test_execution_contract_fields_populated(self):
        sig = build_signal(
            _CANDLE_LONG, _SWEEP_LONG, _DISP_LONG, _ASIAN, "london", _RR, _BUF
        )
        for attr in (
            "side",
            "entry",
            "stop_loss",
            "take_profit",
            "reason",
            "session",
            "timestamp",
        ):
            self.assertIsNotNone(getattr(sig, attr), msg=f"{attr} should not be None")

    def test_timestamp_is_utc_aware(self):
        sig = build_signal(
            _CANDLE_LONG, _SWEEP_LONG, _DISP_LONG, _ASIAN, "london", _RR, _BUF
        )
        self.assertIsNotNone(sig.timestamp.tzinfo)


# ─────────────────────────────────────────────────────────────────────────────
# Category 12 — Timestamp from candle 'time' string
# ─────────────────────────────────────────────────────────────────────────────


class TestTimestamp(unittest.TestCase):

    def test_timestamp_parsed_from_iso_string(self):
        candle = {**_CANDLE_LONG, "time": "2024-01-15T07:45:00Z"}
        sig = build_signal(candle, _SWEEP_LONG, _DISP_LONG, _ASIAN, "london", _RR, _BUF)
        self.assertEqual(sig.timestamp.year, 2024)
        self.assertEqual(sig.timestamp.month, 1)
        self.assertEqual(sig.timestamp.day, 15)
        self.assertEqual(sig.timestamp.hour, 7)
        self.assertEqual(sig.timestamp.minute, 45)

    def test_timestamp_from_datetime_object(self):
        dt = datetime(2024, 7, 15, 11, 30, tzinfo=_UTC)
        candle = {**_CANDLE_LONG, "time": dt}
        sig = build_signal(candle, _SWEEP_LONG, _DISP_LONG, _ASIAN, "london", _RR, _BUF)
        self.assertEqual(sig.timestamp, dt)

    def test_no_time_key_still_returns_signal(self):
        candle = {k: v for k, v in _CANDLE_LONG.items() if k != "time"}
        sig = build_signal(candle, _SWEEP_LONG, _DISP_LONG, _ASIAN, "london", _RR, _BUF)
        self.assertIsNotNone(sig)
        self.assertIsNotNone(sig.timestamp)


# ─────────────────────────────────────────────────────────────────────────────
# Category 14 — Missing candle 'close' key
# ─────────────────────────────────────────────────────────────────────────────


class TestMalformedCandle(unittest.TestCase):

    def test_missing_close_returns_none(self):
        bad = {k: v for k, v in _CANDLE_LONG.items() if k != "close"}
        self.assertIsNone(
            build_signal(bad, _SWEEP_LONG, _DISP_LONG, _ASIAN, "london", _RR, _BUF)
        )

    def test_none_close_returns_none(self):
        self.assertIsNone(
            build_signal(
                {**_CANDLE_LONG, "close": None},
                _SWEEP_LONG,
                _DISP_LONG,
                _ASIAN,
                "london",
                _RR,
                _BUF,
            )
        )

    def test_string_close_returns_none(self):
        self.assertIsNone(
            build_signal(
                {**_CANDLE_LONG, "close": "N/A"},
                _SWEEP_LONG,
                _DISP_LONG,
                _ASIAN,
                "london",
                _RR,
                _BUF,
            )
        )

    def test_none_candle_returns_none(self):
        self.assertIsNone(
            build_signal(None, _SWEEP_LONG, _DISP_LONG, _ASIAN, "london", _RR, _BUF)
        )


# ─────────────────────────────────────────────────────────────────────────────
# Category 18/19 — Risk direction
# ─────────────────────────────────────────────────────────────────────────────


class TestRiskDirection(unittest.TestCase):

    def test_long_risk_is_entry_minus_sl(self):
        sig = build_signal(
            _CANDLE_LONG, _SWEEP_LONG, _DISP_LONG, _ASIAN, "london", _RR, _BUF
        )
        self.assertGreater(sig.entry, sig.stop_loss)
        self.assertAlmostEqual(
            sig.risk_pips, (sig.entry - sig.stop_loss) / 0.0001, places=4
        )

    def test_short_risk_is_sl_minus_entry(self):
        sig = build_signal(
            _CANDLE_SHORT, _SWEEP_SHORT, _DISP_SHORT, _ASIAN, "new_york", _RR, _BUF
        )
        self.assertGreater(sig.stop_loss, sig.entry)
        self.assertAlmostEqual(
            sig.risk_pips, (sig.stop_loss - sig.entry) / 0.0001, places=4
        )


# ─────────────────────────────────────────────────────────────────────────────
# Category 20 — Reason string
# ─────────────────────────────────────────────────────────────────────────────


class TestReasonString(unittest.TestCase):

    def test_long_reason_contains_long(self):
        sig = build_signal(
            _CANDLE_LONG, _SWEEP_LONG, _DISP_LONG, _ASIAN, "london", _RR, _BUF
        )
        self.assertIn("long", sig.reason)

    def test_short_reason_contains_short(self):
        sig = build_signal(
            _CANDLE_SHORT, _SWEEP_SHORT, _DISP_SHORT, _ASIAN, "london", _RR, _BUF
        )
        self.assertIn("short", sig.reason)

    def test_reason_contains_sweep_price(self):
        sig = build_signal(
            _CANDLE_LONG, _SWEEP_LONG, _DISP_LONG, _ASIAN, "london", _RR, _BUF
        )
        self.assertIn(f"{_SWEEP_LONG.sweep_price:.5f}", sig.reason)

    def test_reason_contains_entry(self):
        sig = build_signal(
            _CANDLE_LONG, _SWEEP_LONG, _DISP_LONG, _ASIAN, "london", _RR, _BUF
        )
        self.assertIn(f"{sig.entry:.5f}", sig.reason)

    def test_reason_contains_rr(self):
        sig = build_signal(
            _CANDLE_LONG, _SWEEP_LONG, _DISP_LONG, _ASIAN, "london", _RR, _BUF
        )
        self.assertIn(str(_RR), sig.reason)


if __name__ == "__main__":
    unittest.main()
