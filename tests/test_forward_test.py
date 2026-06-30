"""
DEP-00 — Forward Test Simulator tests.

Validation rules verified:
  A  Signal timestamp == first moment strategy could have known
  B  No signal generated before sweep confirmation
  C  No signal generated before displacement confirmation
  D  One signal max per session
  E  compare_with_backtest() produces identical signal lists
  F  Signal prices match backtest prices exactly

Test categories (10):
  1.  Sequential candle feeding — one at a time, matches batch
  2.  No future candle access  — signal only at displacement bar
  3.  Signal emitted only once — no duplicates on subsequent feeds
  4.  Signal at correct candle — timestamp == displacement bar time
  5.  Multi-day replay         — two independent days, two signals
  6.  Empty dataset            — zero candles → zero signals
  7.  Missing H4 data          — neutral bias → no signals
  8.  Replay output            — timeline contains expected events
  9.  ST-A2 min_sl_pips gate   — filter still enforced in forward mode
  10. Debug timeline            — replay_day / format_replay correctness

Dataset conventions:
  TRADE_DATE = 2024-01-15
  Asian session: 2024-01-14T23:00Z → 2024-01-15T06:45Z (32 × M15 bars)
  London killzone: 07:00–09:45 UTC
  Asian range: high=1.0750, low=1.0700 (50 pip — above EURUSD 15 pip min)
  Sweep bar (07:15): low=1.0682 (breach below), close=1.0720
  Displacement bar (07:30): open=1.0700, high=1.0800, low=1.0695, close=1.0790
  Sweep price: 1.0682  SL: 1.0682 − 0.0002 = 1.0680
  Expected signal timestamp: 2024-01-15T07:30:00Z
"""

import unittest
from datetime import date, datetime, timedelta, timezone

from simulator.forward_test import (
    ForwardTestSimulator,
    ReplayEvent,
    compare_with_backtest,
    format_replay,
    replay_day,
)

_UTC = timezone.utc
TRADE_DATE = date(2024, 1, 15)
DISP_TIME = "2024-01-15T07:30:00Z"


# ─────────────────────────────────────────────────────────────────────────────
# Fixture helpers (mirror test_session_strategy.py conventions)
# ─────────────────────────────────────────────────────────────────────────────


def _bar(
    t: datetime,
    high: float,
    low: float,
    open_: float | None = None,
    close: float | None = None,
) -> dict:
    mid = round((high + low) / 2, 6)
    return {
        "time": t.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "open": open_ if open_ is not None else mid,
        "high": high,
        "low": low,
        "close": close if close is not None else mid,
    }


def _asian_bars(
    trade_date: date = TRADE_DATE,
    high: float = 1.0750,
    low: float = 1.0700,
    n: int = 32,
) -> list[dict]:
    prev = datetime(
        trade_date.year, trade_date.month, trade_date.day, tzinfo=_UTC
    ) - timedelta(days=1)
    start = prev.replace(hour=23, minute=0)
    return [_bar(start + timedelta(minutes=15 * i), high, low) for i in range(n)]


def _h4_bullish(trade_date: date = TRADE_DATE) -> list[dict]:
    highs = [1, 2, 5, 2, 1, 2, 3, 3, 2, 1, 8, 2, 1]
    lows = [0.5, 1, 0.8, 0.5, 0.2, 0.8, 0.5, 0.8, 0.5, 0.3, 1.5, 0.5, 0.2]
    base = datetime(2024, 1, 12, 0, 0, tzinfo=_UTC)
    return [
        _bar(base + timedelta(hours=4 * i), float(h), float(lo))
        for i, (h, lo) in enumerate(zip(highs, lows))
    ]


def _london(
    hour: int,
    minute: int,
    high: float,
    low: float,
    open_: float | None = None,
    close: float | None = None,
    trade_date: date = TRADE_DATE,
) -> dict:
    t = datetime(
        trade_date.year, trade_date.month, trade_date.day, hour, minute, tzinfo=_UTC
    )
    return _bar(t, high, low, open_, close)


def _full_day(trade_date: date = TRADE_DATE) -> list[dict]:
    """32 Asian bars + normal bar + sweep + displacement for one day."""
    bars = _asian_bars(trade_date)
    bars.append(
        _london(7, 0, high=1.0740, low=1.0710, close=1.0730, trade_date=trade_date)
    )
    bars.append(
        _london(
            7,
            15,
            high=1.0748,
            low=1.0682,
            open_=1.0725,
            close=1.0720,
            trade_date=trade_date,
        )
    )
    bars.append(
        _london(
            7,
            30,
            high=1.0800,
            low=1.0695,
            open_=1.0700,
            close=1.0790,
            trade_date=trade_date,
        )
    )
    return bars


# ─────────────────────────────────────────────────────────────────────────────
# Cat 1 — Sequential candle feeding
# ─────────────────────────────────────────────────────────────────────────────


class TestSequentialFeeding(unittest.TestCase):

    def _all_bars(self):
        return _full_day()

    def test_feed_all_matches_batch_count(self):
        """Sequential feed produces the same number of signals as batch."""
        bars, h4 = self._all_bars(), _h4_bullish()
        from strategy.session_liquidity.session_strategy import run_strategy

        bt = run_strategy(bars, h4, "EURUSD")
        sim = ForwardTestSimulator("EURUSD", h4_candles=h4)
        fw = sim.feed_all(bars)
        self.assertEqual(len(bt), len(fw))

    def test_feed_all_matches_batch_timestamps(self):
        """Sequential feed: all signal timestamps equal the batch run."""
        bars, h4 = self._all_bars(), _h4_bullish()
        from strategy.session_liquidity.session_strategy import run_strategy

        bt = run_strategy(bars, h4, "EURUSD")
        sim = ForwardTestSimulator("EURUSD", h4_candles=h4)
        fw = sim.feed_all(bars)
        bt_ts = [s.timestamp.isoformat() for s in bt]
        fw_ts = [s.timestamp.isoformat() for s in fw]
        self.assertEqual(bt_ts, fw_ts)

    def test_compare_with_backtest_reports_match(self):
        """compare_with_backtest() returns match=True on consistent data."""
        bars, h4 = self._all_bars(), _h4_bullish()
        result = compare_with_backtest("EURUSD", bars, h4)
        self.assertTrue(result["match"], result["mismatches"])
        self.assertEqual(result["mismatches"], [])

    def test_compare_with_backtest_counts_agree(self):
        bars, h4 = self._all_bars(), _h4_bullish()
        result = compare_with_backtest("EURUSD", bars, h4)
        self.assertEqual(result["backtest_count"], result["forward_count"])


# ─────────────────────────────────────────────────────────────────────────────
# Cat 2 — No future candle access (validation rule A / B / C)
# ─────────────────────────────────────────────────────────────────────────────


class TestNoFutureAccess(unittest.TestCase):

    def setUp(self):
        self.asian = _asian_bars()
        self.normal = _london(7, 0, high=1.0740, low=1.0710, close=1.0730)
        self.sweep = _london(7, 15, high=1.0748, low=1.0682, open_=1.0725, close=1.0720)
        self.disp = _london(7, 30, high=1.0800, low=1.0695, open_=1.0700, close=1.0790)
        self.h4 = _h4_bullish()

    def test_no_signal_after_asian_only(self):
        """Rule B/C: no signal before sweep or displacement."""
        sim = ForwardTestSimulator("EURUSD", h4_candles=self.h4)
        sigs = sim.feed_all(self.asian)
        self.assertEqual(len(sigs), 0)

    def test_no_signal_after_sweep_only(self):
        """Rule B: no signal after sweep if displacement has not arrived."""
        sim = ForwardTestSimulator("EURUSD", h4_candles=self.h4)
        bars = self.asian + [self.normal, self.sweep]
        sigs = sim.feed_all(bars)
        self.assertEqual(len(sigs), 0)

    def test_signal_appears_on_displacement_candle(self):
        """Rule C: signal fires exactly when displacement candle is fed."""
        sim = ForwardTestSimulator("EURUSD", h4_candles=self.h4)
        sim.feed_all(self.asian + [self.normal, self.sweep])
        new = sim.feed(self.disp)  # displacement bar
        self.assertEqual(len(new), 1)

    def test_signal_timestamp_not_in_future(self):
        """Rule A: signal.timestamp <= time of the candle that triggered it."""
        sim = ForwardTestSimulator("EURUSD", h4_candles=self.h4)
        bars = self.asian + [self.normal, self.sweep, self.disp]
        for candle in bars:
            new = sim.feed(candle)
            candle_time_str = candle["time"]
            for sig in new:
                self.assertLessEqual(
                    sig.timestamp.isoformat().replace("+00:00", "Z"),
                    candle_time_str,
                    f"Signal at {sig.timestamp} appeared before candle {candle_time_str}",
                )


# ─────────────────────────────────────────────────────────────────────────────
# Cat 3 — Signal emitted only once (rule D)
# ─────────────────────────────────────────────────────────────────────────────


class TestSignalOnce(unittest.TestCase):

    def _run(self, extra_london_bars=0):
        bars = _full_day()
        base_t = datetime(2024, 1, 15, 7, 45, tzinfo=_UTC)
        for i in range(extra_london_bars):
            t = base_t + timedelta(minutes=15 * i)
            bars.append(_bar(t, 1.079, 1.075))
        sim = ForwardTestSimulator("EURUSD", h4_candles=_h4_bullish())
        sim.feed_all(bars)
        return sim

    def test_exactly_one_signal_after_full_day(self):
        sim = self._run()
        self.assertEqual(len(sim.signals), 1)

    def test_no_duplicate_after_extra_london_bars(self):
        """Feed 3 more London bars after the signal — still exactly one signal."""
        sim = self._run(extra_london_bars=3)
        self.assertEqual(len(sim.signals), 1)

    def test_candle_count_increments(self):
        sim = ForwardTestSimulator("EURUSD", h4_candles=_h4_bullish())
        bars = _full_day()
        sim.feed_all(bars)
        self.assertEqual(sim.candle_count, len(bars))


# ─────────────────────────────────────────────────────────────────────────────
# Cat 4 — Signal emitted at correct candle (rule A)
# ─────────────────────────────────────────────────────────────────────────────


class TestSignalTiming(unittest.TestCase):

    def setUp(self):
        bars = _full_day()
        h4 = _h4_bullish()
        self.sim = ForwardTestSimulator("EURUSD", h4_candles=h4)
        self.sim.feed_all(bars)

    def test_signal_timestamp_equals_displacement_close_time(self):
        """Rule A: signal.timestamp == bar-close time of displacement candle."""
        sig = self.sim.signals[0]
        self.assertEqual(
            sig.timestamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
            DISP_TIME,
        )

    def test_signal_entry_equals_displacement_close(self):
        """Entry price == close of displacement candle (bar-close execution)."""
        sig = self.sim.signals[0]
        self.assertAlmostEqual(sig.entry, 1.0790, places=4)

    def test_signal_side_is_long(self):
        self.assertEqual(self.sim.signals[0].side, "long")

    def test_signal_session_is_london(self):
        self.assertEqual(self.sim.signals[0].session, "london")


# ─────────────────────────────────────────────────────────────────────────────
# Cat 5 — Multi-day replay
# ─────────────────────────────────────────────────────────────────────────────


class TestMultiDay(unittest.TestCase):

    def _two_days(self):
        d1 = date(2024, 1, 15)
        d2 = date(2024, 1, 16)
        return _full_day(d1) + _full_day(d2), _h4_bullish()

    def test_two_days_two_signals(self):
        bars, h4 = self._two_days()
        sim = ForwardTestSimulator("EURUSD", h4_candles=h4)
        sigs = sim.feed_all(bars)
        self.assertEqual(len(sigs), 2)

    def test_signals_on_different_dates(self):
        bars, h4 = self._two_days()
        sim = ForwardTestSimulator("EURUSD", h4_candles=h4)
        sim.feed_all(bars)
        dates = {s.timestamp.date() for s in sim.signals}
        self.assertEqual(len(dates), 2)

    def test_compare_with_backtest_two_days(self):
        bars, h4 = self._two_days()
        result = compare_with_backtest("EURUSD", bars, h4)
        self.assertTrue(result["match"], result["mismatches"])

    def test_reset_clears_all_state(self):
        bars, h4 = self._two_days()
        sim = ForwardTestSimulator("EURUSD", h4_candles=h4)
        sim.feed_all(bars)
        self.assertEqual(len(sim.signals), 2)
        sim.reset()
        self.assertEqual(len(sim.signals), 0)
        self.assertEqual(sim.candle_count, 0)
        # After reset, same bars produce signals again
        sim.feed_all(bars)
        self.assertEqual(len(sim.signals), 2)


# ─────────────────────────────────────────────────────────────────────────────
# Cat 6 — Empty dataset
# ─────────────────────────────────────────────────────────────────────────────


class TestEmptyDataset(unittest.TestCase):

    def test_feed_no_candles_produces_no_signals(self):
        sim = ForwardTestSimulator("EURUSD", h4_candles=_h4_bullish())
        sigs = sim.feed_all([])
        self.assertEqual(sigs, [])

    def test_candle_count_zero_when_nothing_fed(self):
        sim = ForwardTestSimulator("EURUSD")
        self.assertEqual(sim.candle_count, 0)

    def test_signals_property_empty_initially(self):
        sim = ForwardTestSimulator("EURUSD")
        self.assertEqual(sim.signals, [])

    def test_compare_empty_dataset_matches(self):
        result = compare_with_backtest("EURUSD", [], [], config=None)
        self.assertTrue(result["match"])
        self.assertEqual(result["backtest_count"], 0)
        self.assertEqual(result["forward_count"], 0)


# ─────────────────────────────────────────────────────────────────────────────
# Cat 7 — Missing H4 data
# ─────────────────────────────────────────────────────────────────────────────


class TestMissingH4(unittest.TestCase):

    def test_no_signals_without_h4(self):
        """Without H4 bars, htf_bias returns neutral → no signals."""
        bars = _full_day()
        sim = ForwardTestSimulator("EURUSD", h4_candles=[])
        sigs = sim.feed_all(bars)
        self.assertEqual(len(sigs), 0)

    def test_compare_empty_h4_matches_batch(self):
        bars = _full_day()
        result = compare_with_backtest("EURUSD", bars, h4_candles=[])
        self.assertTrue(result["match"])
        self.assertEqual(result["backtest_count"], 0)
        self.assertEqual(result["forward_count"], 0)


# ─────────────────────────────────────────────────────────────────────────────
# Cat 8 — Replay output correctness (rule replay_day / format_replay)
# ─────────────────────────────────────────────────────────────────────────────


class TestReplayOutput(unittest.TestCase):

    def setUp(self):
        self.bars = _full_day()
        self.h4 = _h4_bullish()
        self.timeline = replay_day(TRADE_DATE, "EURUSD", self.bars, self.h4)

    def test_timeline_is_list_of_replay_events(self):
        self.assertIsInstance(self.timeline, list)
        for ev in self.timeline:
            self.assertIsInstance(ev, ReplayEvent)

    def test_timeline_non_empty(self):
        self.assertGreater(len(self.timeline), 0)

    def test_timeline_has_asian_range_event(self):
        types = [ev.event for ev in self.timeline]
        self.assertIn("ASIAN_RANGE", types)

    def test_timeline_has_sweep_event(self):
        types = [ev.event for ev in self.timeline]
        self.assertIn("SWEEP", types)

    def test_timeline_has_signal_event(self):
        types = [ev.event for ev in self.timeline]
        self.assertIn("SIGNAL", types)

    def test_signal_event_has_time(self):
        sig_ev = next(ev for ev in self.timeline if ev.event == "SIGNAL")
        self.assertIn("UTC", sig_ev.time)

    def test_sweep_event_before_signal_event(self):
        """Sweep must appear before the signal in the timeline."""
        types = [ev.event for ev in self.timeline]
        sweep_idx = types.index("SWEEP")
        signal_idx = types.index("SIGNAL")
        self.assertLess(sweep_idx, signal_idx)

    def test_format_replay_produces_string(self):
        output = format_replay(self.timeline, title="Day Replay")
        self.assertIsInstance(output, str)
        self.assertIn("Day Replay", output)
        self.assertIn("SIGNAL", output)

    def test_replay_day_wrong_date_returns_empty(self):
        other_date = date(2024, 2, 1)
        timeline = replay_day(other_date, "EURUSD", self.bars, self.h4)
        self.assertEqual(timeline, [])


# ─────────────────────────────────────────────────────────────────────────────
# Cat 9 — ST-A2 min_sl_pips still enforced in forward mode
# ─────────────────────────────────────────────────────────────────────────────


class TestSTA2FilterForward(unittest.TestCase):

    def test_default_config_enforces_5pip_floor(self):
        """Default config (min_sl_pips=5.0) passes the 110-pip SL test signal."""
        bars = _full_day()
        sim = ForwardTestSimulator("EURUSD", h4_candles=_h4_bullish())
        sigs = sim.feed_all(bars)
        self.assertEqual(len(sigs), 1)
        self.assertGreaterEqual(sigs[0].risk_pips, 5.0)

    def test_high_min_sl_blocks_signal(self):
        """min_sl_pips=200.0 rejects the 110-pip-SL test signal."""
        bars = _full_day()
        sim = ForwardTestSimulator(
            "EURUSD",
            config={"min_sl_pips": 200.0},
            h4_candles=_h4_bullish(),
        )
        sigs = sim.feed_all(bars)
        self.assertEqual(len(sigs), 0)

    def test_zero_min_sl_still_yields_signal(self):
        """min_sl_pips=0.0 disables filter — backward compat."""
        bars = _full_day()
        sim = ForwardTestSimulator(
            "EURUSD",
            config={"min_sl_pips": 0.0},
            h4_candles=_h4_bullish(),
        )
        sigs = sim.feed_all(bars)
        self.assertEqual(len(sigs), 1)

    def test_filter_consistent_with_backtest(self):
        """Forward and backtest agree when min_sl_pips=200.0 filters everything."""
        bars = _full_day()
        result = compare_with_backtest(
            "EURUSD",
            bars,
            _h4_bullish(),
            config={"min_sl_pips": 200.0},
        )
        self.assertTrue(result["match"])
        self.assertEqual(result["backtest_count"], 0)


# ─────────────────────────────────────────────────────────────────────────────
# Cat 10 — Debug timeline generation
# ─────────────────────────────────────────────────────────────────────────────


class TestDebugTimeline(unittest.TestCase):

    def test_replay_event_dataclass_fields(self):
        ev = ReplayEvent(time="07:30 UTC", event="SIGNAL", detail="london long ...")
        self.assertEqual(ev.time, "07:30 UTC")
        self.assertEqual(ev.event, "SIGNAL")
        self.assertIn("long", ev.detail)

    def test_asian_range_event_has_no_explicit_time(self):
        """ASIAN_RANGE debug event has no bar-label bracket → time=—."""
        timeline = replay_day(TRADE_DATE, "EURUSD", _full_day(), _h4_bullish())
        ar = next(ev for ev in timeline if ev.event == "ASIAN_RANGE")
        self.assertEqual(ar.time, "—")

    def test_signal_event_detail_contains_entry(self):
        timeline = replay_day(TRADE_DATE, "EURUSD", _full_day(), _h4_bullish())
        sig_ev = next(ev for ev in timeline if ev.event == "SIGNAL")
        self.assertIn("entry=", sig_ev.detail)

    def test_format_replay_contains_all_event_types(self):
        timeline = replay_day(TRADE_DATE, "EURUSD", _full_day(), _h4_bullish())
        output = format_replay(timeline)
        self.assertIn("ASIAN_RANGE", output)
        self.assertIn("SWEEP", output)
        self.assertIn("SIGNAL", output)

    def test_format_replay_empty_timeline(self):
        output = format_replay([])
        self.assertIn("Time", output)
        self.assertNotIn("SIGNAL", output)


if __name__ == "__main__":
    unittest.main()
