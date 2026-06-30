"""
Tests for SA-07: session_strategy.py

Required categories:
  1.  End-to-end bullish signal
  2.  End-to-end bearish signal
  3.  No Asian Range (< 4 bars in window)
  4.  Neutral Bias (insufficient H4 swings)
  5.  Sweep Rejected (no breach)
  6.  Displacement Rejected (body too small)
  7.  No killzone bars (only Asian-session M15)
  8.  Multiple Days — one signal per day
  9.  No Duplicate Signals — second sweep in same session ignored
  10. Debug Output — events list populated

Dataset conventions used throughout:
  TRADE_DATE = 2024-01-15 (January = EST winter, UTC-5)
  Asian session (EST 18:00 prev→02:00): 2024-01-14T23:00Z→2024-01-15T06:45Z
  London killzone (EST 02:00→05:00):    2024-01-15T07:00Z→2024-01-15T09:45Z
  Asian range: high=1.0750, low=1.0700  (50 pip, > 15 pip min for EURUSD)
"""

import unittest
from datetime import date, datetime, timedelta, timezone

from strategy.session_liquidity.session_strategy import run_strategy, DEFAULT_CONFIG

_UTC = timezone.utc
TRADE_DATE = date(2024, 1, 15)


# ─────────────────────────────────────────────────────────────────────────────
# Fixture builders
# ─────────────────────────────────────────────────────────────────────────────

def _bar(t: datetime, high: float, low: float,
         open_: float | None = None, close: float | None = None) -> dict:
    mid = round((high + low) / 2, 6)
    return {
        "time":  t.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "open":  open_ if open_ is not None else mid,
        "high":  high,
        "low":   low,
        "close": close if close is not None else mid,
    }


def _asian_bars(trade_date: date = TRADE_DATE,
                high: float = 1.0750, low: float = 1.0700,
                n: int = 32) -> list[dict]:
    """32 M15 bars for the Asian session (23:00 UTC prev → 06:45 UTC)."""
    prev = datetime(trade_date.year, trade_date.month, trade_date.day,
                    tzinfo=_UTC) - timedelta(days=1)
    start = prev.replace(hour=23, minute=0)
    return [_bar(start + timedelta(minutes=15 * i), high, low) for i in range(n)]


def _h4_bullish(trade_date: date = TRADE_DATE) -> list[dict]:
    """
    13 H4 bars starting 2024-01-12T00:00Z producing bullish bias (HH+HL).
    Last bar ends 2024-01-14T00:00Z — well before London cutoff (2024-01-15T03:00Z).
    Highs = [1,2,5,2,1,2,3,3,2,1,8,2,1] → two swing highs at 5 and 8 (HH)
    Lows  = [0.5,1,0.8,0.5,0.2,0.8,0.5,0.8,0.5,0.3,1.5,0.5,0.2]
            → two swing lows at indices 4(0.2) and 9(0.3) are LL actually...
    Use a simpler verified-bullish dataset instead:
    highs = [1,2,3,1,2,4,1,2,5]  → swing highs: 3@2, 4@5, 5@8 → HH (3<4<5) ✓
    lows  = [0.5,0.3,0.8,0.2,0.5,0.8,0.1,0.4,0.7]
            → swing lows: 0.3@1, 0.2@3, 0.1@6 → HL fails (0.3>0.2>0.1 = LL)
    Actually: use test_bias_filter.py's verified bullish dataset:
    highs=[1,2,5,2,1,2,3,3,2,1,8,2,1]
    lows=[0.5,1,0.8,0.5,0.2,0.8,0.5,0.8,0.5,0.3,1.5,0.5,0.2]
    This is verified to return 'bullish' in test_bias_filter.py.
    """
    highs = [1, 2, 5, 2, 1, 2, 3, 3, 2, 1, 8, 2, 1]
    lows  = [0.5, 1, 0.8, 0.5, 0.2, 0.8, 0.5, 0.8, 0.5, 0.3, 1.5, 0.5, 0.2]
    base  = datetime(2024, 1, 12, 0, 0, tzinfo=_UTC)
    return [
        _bar(base + timedelta(hours=4 * i), float(h), float(lo))
        for i, (h, lo) in enumerate(zip(highs, lows))
    ]


def _h4_bearish(trade_date: date = TRADE_DATE) -> list[dict]:
    """13 H4 bars producing bearish bias (LH+LL). Verified in test_bias_filter.py."""
    highs = [1, 2, 8, 2, 1, 2, 3, 3, 2, 1, 5, 2, 1]
    lows  = [0.5, 1.5, 1, 0.5, 0.3, 1, 0.5, 0.8, 0.5, 0.2, 1.5, 0.5, 0.3]
    base  = datetime(2024, 1, 12, 0, 0, tzinfo=_UTC)
    return [
        _bar(base + timedelta(hours=4 * i), float(h), float(lo))
        for i, (h, lo) in enumerate(zip(highs, lows))
    ]


def _h4_neutral() -> list[dict]:
    """3 H4 bars — too few for any swing detection → neutral."""
    base = datetime(2024, 1, 12, 0, 0, tzinfo=_UTC)
    return [
        _bar(base + timedelta(hours=4 * i), 1.08, 1.07)
        for i in range(3)
    ]


def _london_bar(hour: int, minute: int,
                high: float, low: float,
                open_: float | None = None, close: float | None = None,
                trade_date: date = TRADE_DATE) -> dict:
    t = datetime(trade_date.year, trade_date.month, trade_date.day,
                 hour, minute, tzinfo=_UTC)
    return _bar(t, high, low, open_, close)


# ─────────────────────────────────────────────────────────────────────────────
# Category 1 — End-to-end bullish signal
# ─────────────────────────────────────────────────────────────────────────────

class TestEndToEndBullish(unittest.TestCase):
    """
    Setup:
      Asian range:  high=1.0750, low=1.0700  (50 pip)
      07:00 UTC:    Normal bar (no sweep)
      07:15 UTC:    Bullish sweep — low=1.0682 < asian_low, close=1.0720
      07:30 UTC:    Displacement — body=0.0090 > 1.2×ATR(≈0.005), close_pos≈90%
    """

    def setUp(self):
        asian_h, asian_l = 1.0750, 1.0700
        m15 = _asian_bars(high=asian_h, low=asian_l)
        # normal bar — no breach
        m15.append(_london_bar(7, 0,  high=1.0740, low=1.0710, close=1.0730))
        # sweep bar: low < asian_low, close > asian_low
        m15.append(_london_bar(7, 15, high=1.0748, low=1.0682,
                               open_=1.0725, close=1.0720))
        # displacement bar: large bullish body, close in upper 25%
        m15.append(_london_bar(7, 30, high=1.0800, low=1.0695,
                               open_=1.0700, close=1.0790))
        self.sigs = run_strategy(m15, _h4_bullish(), "EURUSD")

    def test_one_signal_generated(self):
        self.assertEqual(len(self.sigs), 1)

    def test_signal_is_long(self):
        self.assertEqual(self.sigs[0].side, "long")

    def test_session_london(self):
        self.assertEqual(self.sigs[0].session, "london")

    def test_entry_is_displacement_close(self):
        self.assertAlmostEqual(self.sigs[0].entry, 1.0790, places=4)

    def test_stop_loss_below_sweep_wick(self):
        # SL = sweep_price(1.0682) - 2pip(0.0002) = 1.0680
        self.assertAlmostEqual(self.sigs[0].stop_loss, 1.0680, places=4)

    def test_tp_above_entry(self):
        self.assertGreater(self.sigs[0].take_profit, self.sigs[0].entry)

    def test_risk_pips_positive(self):
        self.assertGreater(self.sigs[0].risk_pips, 0)

    def test_rr_is_default(self):
        self.assertEqual(self.sigs[0].rr, DEFAULT_CONFIG["rr"])


# ─────────────────────────────────────────────────────────────────────────────
# Category 2 — End-to-end bearish signal
# ─────────────────────────────────────────────────────────────────────────────

class TestEndToEndBearish(unittest.TestCase):
    """
    Asian range: high=1.0750, low=1.0700
    07:00 UTC: normal bar
    07:15 UTC: bearish sweep — high=1.0768 > asian_high, close=1.0740
    07:30 UTC: displacement — large bearish body, close in lower 25%
    """

    def setUp(self):
        asian_h, asian_l = 1.0750, 1.0700
        m15 = _asian_bars(high=asian_h, low=asian_l)
        m15.append(_london_bar(7, 0,  high=1.0745, low=1.0710, close=1.0725))
        # bearish sweep: high > asian_high, close < asian_high
        m15.append(_london_bar(7, 15, high=1.0768, low=1.0710,
                               open_=1.0730, close=1.0740))
        # bearish displacement: large down body, close in lower 25%
        m15.append(_london_bar(7, 30, high=1.0755, low=1.0645,
                               open_=1.0750, close=1.0660))
        self.sigs = run_strategy(m15, _h4_bearish(), "EURUSD")

    def test_one_signal_generated(self):
        self.assertEqual(len(self.sigs), 1)

    def test_signal_is_short(self):
        self.assertEqual(self.sigs[0].side, "short")

    def test_session_london(self):
        self.assertEqual(self.sigs[0].session, "london")

    def test_entry_is_displacement_close(self):
        self.assertAlmostEqual(self.sigs[0].entry, 1.0660, places=4)

    def test_stop_loss_above_sweep_wick(self):
        # SL = sweep_price(1.0768) + 2pip(0.0002) = 1.0770
        self.assertAlmostEqual(self.sigs[0].stop_loss, 1.0770, places=4)

    def test_tp_below_entry(self):
        self.assertLess(self.sigs[0].take_profit, self.sigs[0].entry)


# ─────────────────────────────────────────────────────────────────────────────
# Category 3 — No Asian Range
# ─────────────────────────────────────────────────────────────────────────────

class TestNoAsianRange(unittest.TestCase):

    def test_fewer_than_4_asian_bars_returns_no_signals(self):
        # Only 3 Asian bars → build_asian_range returns None
        m15 = _asian_bars(n=3)
        # Add a valid London setup so the only rejection is missing Asian range
        m15.append(_london_bar(7, 15, high=1.0748, low=1.0682, close=1.0720))
        m15.append(_london_bar(7, 30, high=1.0800, low=1.0695, close=1.0790))
        sigs = run_strategy(m15, _h4_bullish(), "EURUSD")
        self.assertEqual(len(sigs), 0)

    def test_empty_m15_returns_no_signals(self):
        sigs = run_strategy([], _h4_bullish(), "EURUSD")
        self.assertEqual(len(sigs), 0)

    def test_no_asian_range_debug_event_recorded(self):
        m15 = _asian_bars(n=3)
        m15.append(_london_bar(7, 15, high=1.0748, low=1.0682, close=1.0720))
        sigs, events = run_strategy(m15, _h4_bullish(), "EURUSD", debug=True)
        self.assertEqual(len(sigs), 0)
        skip_events = [e for e in events if e["event"] == "SKIP_DAY"]
        self.assertTrue(len(skip_events) >= 1)


# ─────────────────────────────────────────────────────────────────────────────
# Category 4 — Neutral Bias
# ─────────────────────────────────────────────────────────────────────────────

class TestNeutralBias(unittest.TestCase):

    def test_neutral_bias_no_signals(self):
        m15 = _asian_bars()
        m15.append(_london_bar(7, 15, high=1.0748, low=1.0682, close=1.0720))
        m15.append(_london_bar(7, 30, high=1.0800, low=1.0695, close=1.0790))
        sigs = run_strategy(m15, _h4_neutral(), "EURUSD")
        self.assertEqual(len(sigs), 0)

    def test_neutral_bias_debug_shows_no_trade_event(self):
        m15 = _asian_bars()
        m15.append(_london_bar(7, 15, high=1.0748, low=1.0682, close=1.0720))
        sigs, events = run_strategy(m15, _h4_neutral(), "EURUSD", debug=True)
        self.assertEqual(len(sigs), 0)
        no_trade = [e for e in events if e["event"] == "NO_TRADE"]
        self.assertGreater(len(no_trade), 0)


# ─────────────────────────────────────────────────────────────────────────────
# Category 5 — Sweep Rejected
# ─────────────────────────────────────────────────────────────────────────────

class TestSweepRejected(unittest.TestCase):

    def test_no_breach_returns_no_signal(self):
        # London bars that stay inside the Asian range → no sweep
        m15 = _asian_bars()
        for h in range(7, 10):    # 07:00–09:45 UTC (London killzone)
            for m in range(0, 60, 15):
                m15.append(_london_bar(h, m, high=1.0745, low=1.0710, close=1.0725))
        sigs = run_strategy(m15, _h4_bullish(), "EURUSD")
        self.assertEqual(len(sigs), 0)

    def test_breach_but_close_outside_returns_no_signal(self):
        # Low < asian_low but close also < asian_low → close_outside_range → no sweep
        m15 = _asian_bars()
        # low=1.0682 < 1.0700, but close=1.0695 also < 1.0700 → rejected
        m15.append(_london_bar(7, 15, high=1.0740, low=1.0682, close=1.0695))
        sigs = run_strategy(m15, _h4_bullish(), "EURUSD")
        self.assertEqual(len(sigs), 0)

    def test_sweep_rejected_event_in_debug(self):
        m15 = _asian_bars()
        m15.append(_london_bar(7, 15, high=1.0745, low=1.0710, close=1.0725))
        sigs, events = run_strategy(m15, _h4_bullish(), "EURUSD", debug=True)
        self.assertEqual(len(sigs), 0)
        no_sweep = [e for e in events if e["event"] == "NO_SWEEP"]
        self.assertGreater(len(no_sweep), 0)


# ─────────────────────────────────────────────────────────────────────────────
# Category 6 — Displacement Rejected
# ─────────────────────────────────────────────────────────────────────────────

class TestDisplacementRejected(unittest.TestCase):

    def _weak_bars(self, n: int, start_h: int) -> list[dict]:
        """Small-body bars that fail displacement gate."""
        bars = []
        for i in range(n):
            m = (start_h * 60 + 15 * i) % 60
            h_off = (start_h * 60 + 15 * i) // 60
            bars.append(_london_bar(h_off, m,
                                    high=1.0730, low=1.0720,
                                    open_=1.0725, close=1.0726))
        return bars

    def test_all_displacement_bars_fail_times_out(self):
        m15 = _asian_bars()
        sweep_t = datetime(2024, 1, 15, 7, 15, tzinfo=_UTC)
        # sweep bar
        m15.append(_bar(sweep_t, high=1.0748, low=1.0682,
                        open_=1.0725, close=1.0720))
        # 4 weak displacement attempts (body ≈ 0.0001 << threshold)
        for i in range(1, 5):
            t = sweep_t + timedelta(minutes=15 * i)
            m15.append(_bar(t, high=1.0730, low=1.0720, open_=1.0725, close=1.0726))
        sigs = run_strategy(m15, _h4_bullish(), "EURUSD")
        self.assertEqual(len(sigs), 0)

    def test_timeout_event_in_debug(self):
        m15 = _asian_bars()
        sweep_t = datetime(2024, 1, 15, 7, 15, tzinfo=_UTC)
        m15.append(_bar(sweep_t, high=1.0748, low=1.0682, close=1.0720))
        for i in range(1, 6):
            t = sweep_t + timedelta(minutes=15 * i)
            m15.append(_bar(t, high=1.0730, low=1.0720, open_=1.0725, close=1.0726))
        sigs, events = run_strategy(m15, _h4_bullish(), "EURUSD", debug=True)
        self.assertEqual(len(sigs), 0)
        self.assertTrue(any(e["event"] == "SWEEP_TIMEOUT" for e in events))

    def test_disp_reject_event_in_debug(self):
        m15 = _asian_bars()
        m15.append(_london_bar(7, 15, high=1.0748, low=1.0682, close=1.0720))
        m15.append(_london_bar(7, 30, high=1.0730, low=1.0720,
                               open_=1.0725, close=1.0726))
        sigs, events = run_strategy(m15, _h4_bullish(), "EURUSD", debug=True)
        self.assertTrue(any(e["event"] == "DISP_REJECT" for e in events))


# ─────────────────────────────────────────────────────────────────────────────
# Category 7 — No killzone bars
# ─────────────────────────────────────────────────────────────────────────────

class TestNoKillzoneBars(unittest.TestCase):

    def test_only_asian_bars_no_signals(self):
        # Pure Asian session bars — none in London or NY
        m15 = _asian_bars(n=32)
        sigs = run_strategy(m15, _h4_bullish(), "EURUSD")
        self.assertEqual(len(sigs), 0)

    def test_empty_candles_no_signals(self):
        sigs = run_strategy([], _h4_bullish(), "EURUSD")
        self.assertEqual(len(sigs), 0)


# ─────────────────────────────────────────────────────────────────────────────
# Category 8 — Multiple Days
# ─────────────────────────────────────────────────────────────────────────────

class TestMultipleDays(unittest.TestCase):

    def _day_candles(self, trade_date: date) -> list[dict]:
        """Full dataset for one day: 32 Asian + sweep + displacement."""
        prev = datetime(trade_date.year, trade_date.month, trade_date.day,
                        tzinfo=_UTC) - timedelta(days=1)
        asian_start = prev.replace(hour=23, minute=0)
        bars = [
            _bar(asian_start + timedelta(minutes=15 * i), 1.0750, 1.0700)
            for i in range(32)
        ]
        london_7 = datetime(trade_date.year, trade_date.month, trade_date.day,
                            7, 0, tzinfo=_UTC)
        bars.append(_bar(london_7,               1.0748, 1.0682, 1.0725, 1.0720))
        bars.append(_bar(london_7 + timedelta(minutes=15), 1.0800, 1.0695, 1.0700, 1.0790))
        return bars

    def test_two_days_two_signals(self):
        d1 = date(2024, 1, 15)
        d2 = date(2024, 1, 16)
        m15 = self._day_candles(d1) + self._day_candles(d2)
        sigs = run_strategy(m15, _h4_bullish(), "EURUSD")
        self.assertEqual(len(sigs), 2)

    def test_signals_on_different_dates(self):
        d1 = date(2024, 1, 15)
        d2 = date(2024, 1, 16)
        m15 = self._day_candles(d1) + self._day_candles(d2)
        sigs = run_strategy(m15, _h4_bullish(), "EURUSD")
        ts_dates = {s.timestamp.date() for s in sigs}
        self.assertEqual(len(ts_dates), 2)


# ─────────────────────────────────────────────────────────────────────────────
# Category 9 — No Duplicate Signals
# ─────────────────────────────────────────────────────────────────────────────

class TestNoDuplicateSignals(unittest.TestCase):

    def test_second_sweep_in_same_session_ignored(self):
        """After a signal fires in London, later London bars are skipped."""
        m15 = _asian_bars()
        # First sweep + displacement → signal
        m15.append(_london_bar(7, 15, high=1.0748, low=1.0682,
                               open_=1.0725, close=1.0720))
        m15.append(_london_bar(7, 30, high=1.0800, low=1.0695,
                               open_=1.0700, close=1.0790))
        # Second sweep later in London (08:30, 08:45) — should be skipped
        m15.append(_london_bar(8, 30, high=1.0748, low=1.0682,
                               open_=1.0725, close=1.0720))
        m15.append(_london_bar(8, 45, high=1.0800, low=1.0695,
                               open_=1.0700, close=1.0790))
        sigs = run_strategy(m15, _h4_bullish(), "EURUSD")
        self.assertEqual(len(sigs), 1)

    def test_london_and_ny_can_both_fire(self):
        """London and NY are separate sessions — both can generate a signal."""
        m15 = _asian_bars()
        # London signal
        m15.append(_london_bar(7, 15, high=1.0748, low=1.0682,
                               open_=1.0725, close=1.0720))
        m15.append(_london_bar(7, 30, high=1.0800, low=1.0695,
                               open_=1.0700, close=1.0790))
        # NY signal (12:00–14:45 UTC for EST winter)
        m15.append(_london_bar(12, 15, high=1.0748, low=1.0682,
                               open_=1.0725, close=1.0720))
        m15.append(_london_bar(12, 30, high=1.0800, low=1.0695,
                               open_=1.0700, close=1.0790))
        sigs = run_strategy(m15, _h4_bullish(), "EURUSD")
        sessions = {s.session for s in sigs}
        self.assertIn("london", sessions)
        self.assertIn("new_york", sessions)


# ─────────────────────────────────────────────────────────────────────────────
# Category 10 — Debug Output
# ─────────────────────────────────────────────────────────────────────────────

class TestDebugOutput(unittest.TestCase):

    def _run_debug(self):
        m15 = _asian_bars()
        m15.append(_london_bar(7, 15, high=1.0748, low=1.0682,
                               open_=1.0725, close=1.0720))
        m15.append(_london_bar(7, 30, high=1.0800, low=1.0695,
                               open_=1.0700, close=1.0790))
        return run_strategy(m15, _h4_bullish(), "EURUSD", debug=True)

    def test_debug_true_returns_tuple(self):
        result = self._run_debug()
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)

    def test_debug_first_element_is_signals(self):
        sigs, _ = self._run_debug()
        self.assertIsInstance(sigs, list)
        self.assertEqual(len(sigs), 1)

    def test_debug_second_element_is_events_list(self):
        _, events = self._run_debug()
        self.assertIsInstance(events, list)

    def test_events_non_empty(self):
        _, events = self._run_debug()
        self.assertGreater(len(events), 0)

    def test_events_have_required_keys(self):
        _, events = self._run_debug()
        for e in events:
            self.assertIn("date", e)
            self.assertIn("event", e)
            self.assertIn("detail", e)

    def test_asian_range_event_present(self):
        _, events = self._run_debug()
        self.assertTrue(any(e["event"] == "ASIAN_RANGE" for e in events))

    def test_sweep_event_present(self):
        _, events = self._run_debug()
        self.assertTrue(any(e["event"] == "SWEEP" for e in events))

    def test_signal_event_present(self):
        _, events = self._run_debug()
        self.assertTrue(any(e["event"] == "SIGNAL" for e in events))

    def test_debug_false_returns_list_not_tuple(self):
        m15 = _asian_bars()
        result = run_strategy(m15, _h4_bullish(), "EURUSD", debug=False)
        self.assertIsInstance(result, list)

    def test_signal_event_contains_entry_price(self):
        _, events = self._run_debug()
        sig_events = [e for e in events if e["event"] == "SIGNAL"]
        self.assertTrue(len(sig_events) >= 1)
        self.assertIn("entry=", sig_events[0]["detail"])


# ─────────────────────────────────────────────────────────────────────────────
# Additional: config overrides
# ─────────────────────────────────────────────────────────────────────────────

class TestConfigOverrides(unittest.TestCase):

    def _base_m15(self):
        m15 = _asian_bars()
        m15.append(_london_bar(7, 15, high=1.0748, low=1.0682,
                               open_=1.0725, close=1.0720))
        m15.append(_london_bar(7, 30, high=1.0800, low=1.0695,
                               open_=1.0700, close=1.0790))
        return m15

    def test_custom_rr_applied(self):
        sigs = run_strategy(self._base_m15(), _h4_bullish(), "EURUSD",
                            config={"rr": 5.0})
        self.assertEqual(len(sigs), 1)
        self.assertEqual(sigs[0].rr, 5.0)

    def test_min_range_too_high_skips_day(self):
        # Asian range = 50 pips; set min to 200 → day skipped
        sigs = run_strategy(self._base_m15(), _h4_bullish(), "EURUSD",
                            config={"min_range_pips": {"EURUSD": 200.0}})
        self.assertEqual(len(sigs), 0)

    def test_none_config_uses_defaults(self):
        sigs = run_strategy(self._base_m15(), _h4_bullish(), "EURUSD", config=None)
        self.assertEqual(len(sigs), 1)
        self.assertEqual(sigs[0].rr, DEFAULT_CONFIG["rr"])


# ─────────────────────────────────────────────────────────────────────────────
# ST-A2 — min_sl_pips filter (Category 11)
# ─────────────────────────────────────────────────────────────────────────────

class TestMinSlPipsFilter(unittest.TestCase):
    """
    ST-A2 gate: signals with risk_pips < min_sl_pips are rejected before output.
    Base setup produces ~110 pip risk (entry=1.0790, SL=1.0680).
    Filter tested via config overrides — no fixture changes needed.
    """

    def _base_m15(self):
        m15 = _asian_bars()
        m15.append(_london_bar(7, 0,  high=1.0740, low=1.0710, close=1.0730))
        m15.append(_london_bar(7, 15, high=1.0748, low=1.0682,
                               open_=1.0725, close=1.0720))
        m15.append(_london_bar(7, 30, high=1.0800, low=1.0695,
                               open_=1.0700, close=1.0790))
        return m15

    def test_default_config_has_min_sl_pips(self):
        self.assertIn("min_sl_pips", DEFAULT_CONFIG)
        self.assertEqual(DEFAULT_CONFIG["min_sl_pips"], 5.0)

    def test_signal_passes_when_risk_above_threshold(self):
        sigs = run_strategy(self._base_m15(), _h4_bullish(), "EURUSD")
        self.assertEqual(len(sigs), 1)
        self.assertGreaterEqual(sigs[0].risk_pips, 5.0)

    def test_signal_rejected_when_threshold_exceeds_risk(self):
        sigs = run_strategy(
            self._base_m15(), _h4_bullish(), "EURUSD",
            config={"min_sl_pips": 200.0},
        )
        self.assertEqual(len(sigs), 0)

    def test_zero_min_sl_pips_is_pass_through(self):
        sigs = run_strategy(
            self._base_m15(), _h4_bullish(), "EURUSD",
            config={"min_sl_pips": 0.0},
        )
        self.assertEqual(len(sigs), 1)

    def test_min_sl_rejection_fires_debug_event(self):
        _, events = run_strategy(
            self._base_m15(), _h4_bullish(), "EURUSD",
            config={"min_sl_pips": 200.0},
            debug=True,
        )
        rejected = [e for e in events if e["event"] == "SIGNAL_REJECTED"]
        self.assertGreater(len(rejected), 0)
        self.assertTrue(any("min_sl" in e["detail"] for e in rejected))

    def test_exact_threshold_boundary_passes(self):
        sigs = run_strategy(self._base_m15(), _h4_bullish(), "EURUSD")
        risk = sigs[0].risk_pips
        sigs2 = run_strategy(
            self._base_m15(), _h4_bullish(), "EURUSD",
            config={"min_sl_pips": risk},
        )
        self.assertEqual(len(sigs2), 1)

    def test_one_above_boundary_is_rejected(self):
        sigs = run_strategy(self._base_m15(), _h4_bullish(), "EURUSD")
        risk = sigs[0].risk_pips
        sigs2 = run_strategy(
            self._base_m15(), _h4_bullish(), "EURUSD",
            config={"min_sl_pips": risk + 0.1},
        )
        self.assertEqual(len(sigs2), 0)

    def test_bearish_signal_also_filtered(self):
        m15 = _asian_bars()
        m15.append(_london_bar(7, 0,  high=1.0745, low=1.0710, close=1.0725))
        m15.append(_london_bar(7, 15, high=1.0768, low=1.0710,
                               open_=1.0730, close=1.0740))
        m15.append(_london_bar(7, 30, high=1.0755, low=1.0645,
                               open_=1.0750, close=1.0660))
        sigs_pass = run_strategy(m15, _h4_bearish(), "EURUSD")
        self.assertEqual(len(sigs_pass), 1)
        risk = sigs_pass[0].risk_pips
        sigs_block = run_strategy(
            m15, _h4_bearish(), "EURUSD",
            config={"min_sl_pips": risk + 0.1},
        )
        self.assertEqual(len(sigs_block), 0)


class TestV2SessionMode(unittest.TestCase):
    def test_overlap_session_signal_is_supported(self):
        m15 = _asian_bars()
        # Overlap sweep + displacement using the V2 session classifier.
        m15.append(_london_bar(12, 15, high=1.0748, low=1.0682,
                               open_=1.0725, close=1.0720))
        m15.append(_london_bar(12, 30, high=1.0800, low=1.0695,
                               open_=1.0700, close=1.0790))

        sigs = run_strategy(
            m15,
            _h4_bullish(),
            "EURUSD",
            config={"session_mode": "v2"},
        )

        self.assertEqual(len(sigs), 1)
        self.assertEqual(sigs[0].session, "overlap")
        self.assertEqual(sigs[0].side, "long")


if __name__ == "__main__":
    unittest.main()
