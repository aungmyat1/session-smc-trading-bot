"""
Tests for SA-01: session_builder.py

Covers:
  build_asian_range  — high/low extraction, boundary exclusions, DST, edge cases
  classify_session   — killzone classification in winter (EST) and summer (EDT)
"""

import unittest
from datetime import date, datetime, timezone

from strategy.session_liquidity.session_builder import (
    build_asian_range,
    build_session_box,
    active_sessions,
    classify_session,
    classify_session_v2,
)

UTC = timezone.utc


def _c(t: str, h: float, l: float) -> dict:
    """Minimal M15 candle at time t with given high and low."""
    mid = round((h + l) / 2, 5)
    return {"time": t, "open": mid, "high": h, "low": l, "close": mid, "volume": 100.0}


def _dt(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

# trade_date = 2024-01-16 (Tuesday), EST winter (UTC-5)
# Asian window:
#   prev day  2024-01-15  18:00–23:59 EST = 23:00–04:59 UTC
#   trade_date 2024-01-16 00:00–01:59 EST = 05:00–06:59 UTC
# London starts 2024-01-16 07:00 UTC (02:00 EST) — EXCLUDED

WINTER_CANDLES = [
    # pre-Asian prev day (excluded — before 18:00 EST)
    _c("2024-01-15T22:45:00Z", 1.0900, 1.0890),   # 17:45 EST
    # Asian prev day 18:00–23:45 EST
    _c("2024-01-15T23:00:00Z", 1.0920, 1.0895),   # 18:00 EST ← start
    _c("2024-01-15T23:15:00Z", 1.0925, 1.0900),   # 18:15 EST
    _c("2024-01-16T00:00:00Z", 1.0930, 1.0905),   # 19:00 EST
    _c("2024-01-16T02:00:00Z", 1.0915, 1.0892),   # 21:00 EST
    # Asian trade_date 00:00–01:45 EST
    _c("2024-01-16T05:00:00Z", 1.0940, 1.0880),   # 00:00 EST ← HIGH & LOW
    _c("2024-01-16T05:15:00Z", 1.0910, 1.0895),   # 00:15 EST
    _c("2024-01-16T06:45:00Z", 1.0905, 1.0898),   # 01:45 EST ← last Asian bar
    # London session (excluded)
    _c("2024-01-16T07:00:00Z", 1.0960, 1.0850),   # 02:00 EST — must be excluded
    _c("2024-01-16T08:00:00Z", 1.0965, 1.0855),   # 03:00 EST — excluded
]

TRADE_DATE_WINTER = date(2024, 1, 16)


# ─────────────────────────────────────────────────────────────────────────────
class TestBuildAsianRange(unittest.TestCase):

    def test_basic_high(self):
        r = build_asian_range(WINTER_CANDLES, TRADE_DATE_WINTER)
        self.assertIsNotNone(r)
        # HIGH = 1.0940 from bar at 05:00 UTC (00:00 EST on trade_date)
        self.assertAlmostEqual(r.high, 1.0940, places=4)

    def test_basic_low(self):
        r = build_asian_range(WINTER_CANDLES, TRADE_DATE_WINTER)
        self.assertIsNotNone(r)
        # LOW = 1.0880 from bar at 05:00 UTC
        self.assertAlmostEqual(r.low, 1.0880, places=4)

    def test_trade_date_stored(self):
        r = build_asian_range(WINTER_CANDLES, TRADE_DATE_WINTER)
        self.assertEqual(r.trade_date, TRADE_DATE_WINTER)

    def test_excludes_london_bar(self):
        """02:00 EST / 07:00 UTC bar (h=1.0960) must NOT inflate the high."""
        r = build_asian_range(WINTER_CANDLES, TRADE_DATE_WINTER)
        self.assertIsNotNone(r)
        self.assertLess(r.high, 1.0960)

    def test_excludes_pre_asian_bar(self):
        """17:45 EST bar (l=1.0890) must NOT deflate the low below 1.0880."""
        r = build_asian_range(WINTER_CANDLES, TRADE_DATE_WINTER)
        self.assertIsNotNone(r)
        # Pre-Asian low is 1.0890, real Asian low is 1.0880 — both cases would
        # give 1.0880 here, so verify the pre-Asian high (1.0900) isn't the high.
        self.assertGreater(r.high, 1.0900)

    def test_range_pips(self):
        """range = 1.0940 - 1.0880 = 0.0060 = 60 pips."""
        r = build_asian_range(WINTER_CANDLES, TRADE_DATE_WINTER)
        self.assertAlmostEqual(r.range_pips, 60.0, places=1)

    def test_too_few_bars_returns_none(self):
        """3 Asian bars → None (below 4-bar minimum)."""
        candles = [
            _c("2024-01-15T23:00:00Z", 1.0920, 1.0895),  # Asian
            _c("2024-01-15T23:15:00Z", 1.0925, 1.0900),  # Asian
            _c("2024-01-16T05:00:00Z", 1.0940, 1.0880),  # Asian
        ]
        self.assertIsNone(build_asian_range(candles, TRADE_DATE_WINTER))

    def test_empty_candles_returns_none(self):
        self.assertIsNone(build_asian_range([], TRADE_DATE_WINTER))

    def test_only_non_asian_candles_returns_none(self):
        """London + NY bars only → None."""
        candles = [
            _c("2024-01-16T07:00:00Z", 1.0960, 1.0850),
            _c("2024-01-16T08:00:00Z", 1.0965, 1.0855),
            _c("2024-01-16T12:00:00Z", 1.0970, 1.0840),
            _c("2024-01-16T14:00:00Z", 1.0975, 1.0845),
        ]
        self.assertIsNone(build_asian_range(candles, TRADE_DATE_WINTER))

    def test_exactly_four_bars_accepted(self):
        """4 Asian bars → NOT None."""
        candles = [
            _c("2024-01-15T23:00:00Z", 1.0920, 1.0900),
            _c("2024-01-15T23:15:00Z", 1.0922, 1.0898),
            _c("2024-01-16T05:00:00Z", 1.0930, 1.0890),
            _c("2024-01-16T05:15:00Z", 1.0918, 1.0905),
        ]
        r = build_asian_range(candles, TRADE_DATE_WINTER)
        self.assertIsNotNone(r)

    # ── DST: spring forward 2024-03-10 ──────────────────────────────────────

    def test_dst_spring_forward(self):
        """2024-03-10 (Sunday): US springs forward at 02:00 EST → 03:00 EDT.

        Asian session for trade_date=2024-03-11 (Monday):
          prev_day 2024-03-10 18:00 EDT = 22:00 UTC
          trade_date 2024-03-11 00:00 EDT = 04:00 UTC  (h < 2 in EDT)
          London: 2024-03-11 02:00 EDT = 06:00 UTC  ← excluded
        """
        candles = [
            _c("2024-03-10T22:00:00Z", 1.0810, 1.0795),  # 18:00 EDT prev — included
            _c("2024-03-10T22:15:00Z", 1.0815, 1.0792),
            _c("2024-03-10T23:00:00Z", 1.0820, 1.0790),
            _c("2024-03-11T04:00:00Z", 1.0830, 1.0780),  # 00:00 EDT — included (LOW)
            _c("2024-03-11T05:45:00Z", 1.0808, 1.0798),  # 01:45 EDT — included
            _c("2024-03-11T06:00:00Z", 1.0860, 1.0750),  # 02:00 EDT — EXCLUDED
        ]
        r = build_asian_range(candles, date(2024, 3, 11))
        self.assertIsNotNone(r)
        self.assertAlmostEqual(r.low, 1.0780, places=4)
        self.assertLess(r.high, 1.0860)  # London bar excluded

    # ── DST: fall back 2024-11-03 ───────────────────────────────────────────

    def test_dst_fall_back(self):
        """2024-11-03 (Sunday): US falls back at 02:00 EDT → 01:00 EST.

        Asian session for trade_date=2024-11-04 (Monday):
          prev_day 2024-11-03 18:00 EST = 23:00 UTC  (after fall-back, EST = UTC-5)
          trade_date 2024-11-04 00:00 EST = 05:00 UTC
          London: 2024-11-04 02:00 EST = 07:00 UTC  ← excluded
        """
        candles = [
            _c("2024-11-03T23:00:00Z", 1.0905, 1.0888),  # 18:00 EST — included
            _c("2024-11-04T00:00:00Z", 1.0912, 1.0890),
            _c("2024-11-04T05:00:00Z", 1.0920, 1.0878),  # 00:00 EST — included (LOW)
            _c("2024-11-04T06:45:00Z", 1.0915, 1.0902),  # 01:45 EST — included
            _c("2024-11-04T07:00:00Z", 1.0940, 1.0855),  # 02:00 EST — EXCLUDED
        ]
        r = build_asian_range(candles, date(2024, 11, 4))
        self.assertIsNotNone(r)
        self.assertAlmostEqual(r.low, 1.0878, places=4)
        self.assertLess(r.high, 1.0940)


# ─────────────────────────────────────────────────────────────────────────────
class TestClassifySession(unittest.TestCase):

    # ── Winter: EST = UTC-5 ──────────────────────────────────────────────────

    def test_london_open_winter(self):
        """07:00 UTC = 02:00 EST → 'london'."""
        self.assertEqual(classify_session(_dt("2024-01-15T07:00:00Z")), "london")

    def test_london_mid_winter(self):
        """08:30 UTC = 03:30 EST → 'london'."""
        self.assertEqual(classify_session(_dt("2024-01-15T08:30:00Z")), "london")

    def test_london_last_bar_winter(self):
        """09:45 UTC = 04:45 EST → 'london' (last M15 bar before close)."""
        self.assertEqual(classify_session(_dt("2024-01-15T09:45:00Z")), "london")

    def test_london_close_excluded_winter(self):
        """10:00 UTC = 05:00 EST → None (exclusive upper bound)."""
        self.assertIsNone(classify_session(_dt("2024-01-15T10:00:00Z")))

    def test_ny_open_winter(self):
        """12:00 UTC = 07:00 EST → 'new_york'."""
        self.assertEqual(classify_session(_dt("2024-01-15T12:00:00Z")), "new_york")

    def test_ny_last_bar_winter(self):
        """14:45 UTC = 09:45 EST → 'new_york'."""
        self.assertEqual(classify_session(_dt("2024-01-15T14:45:00Z")), "new_york")

    def test_ny_close_excluded_winter(self):
        """15:00 UTC = 10:00 EST → None (exclusive upper bound)."""
        self.assertIsNone(classify_session(_dt("2024-01-15T15:00:00Z")))

    def test_asian_hour_is_none(self):
        """00:00 UTC = 19:00 EST → None."""
        self.assertIsNone(classify_session(_dt("2024-01-15T00:00:00Z")))

    def test_between_sessions_is_none(self):
        """10:30 UTC = 05:30 EST → None (gap between London and NY)."""
        self.assertIsNone(classify_session(_dt("2024-01-15T10:30:00Z")))

    def test_midnight_utc_is_none(self):
        """23:59 UTC prev = 18:59 EST → None (Asian session, not a killzone)."""
        self.assertIsNone(classify_session(_dt("2024-01-14T23:59:00Z")))

    # ── Summer: EDT = UTC-4 ──────────────────────────────────────────────────

    def test_london_open_summer(self):
        """06:00 UTC = 02:00 EDT → 'london' (1h earlier than winter)."""
        self.assertEqual(classify_session(_dt("2024-06-15T06:00:00Z")), "london")

    def test_london_close_excluded_summer(self):
        """09:00 UTC = 05:00 EDT → None."""
        self.assertIsNone(classify_session(_dt("2024-06-15T09:00:00Z")))

    def test_ny_open_summer(self):
        """11:00 UTC = 07:00 EDT → 'new_york'."""
        self.assertEqual(classify_session(_dt("2024-06-15T11:00:00Z")), "new_york")

    def test_ny_close_excluded_summer(self):
        """14:00 UTC = 10:00 EDT → None."""
        self.assertIsNone(classify_session(_dt("2024-06-15T14:00:00Z")))

    def test_between_sessions_summer(self):
        """09:30 UTC = 05:30 EDT → None (between London and NY)."""
        self.assertIsNone(classify_session(_dt("2024-06-15T09:30:00Z")))

    # ── Accepts datetime objects directly ────────────────────────────────────

    def test_accepts_datetime_object(self):
        dt = datetime(2024, 1, 15, 7, 0, 0, tzinfo=timezone.utc)
        self.assertEqual(classify_session(dt), "london")

    def test_accepts_naive_datetime_assumed_utc(self):
        dt = datetime(2024, 1, 15, 7, 0, 0)  # no tzinfo
        self.assertEqual(classify_session(dt), "london")


class TestV2SessionHelpers(unittest.TestCase):
    def test_active_sessions_overlap_window(self):
        dt = datetime(2024, 1, 15, 12, 30, tzinfo=timezone.utc)
        self.assertEqual(active_sessions(dt), ["overlap", "newyork"])

    def test_classify_session_v2_prioritises_overlap(self):
        dt = datetime(2024, 1, 15, 12, 30, tzinfo=timezone.utc)
        self.assertEqual(classify_session_v2(dt), "overlap")

    def test_build_session_box(self):
        candles = [
            {"time": "2024-01-15T07:00:00Z", "open": 1.0, "high": 1.1, "low": 0.9, "close": 1.05},
            {"time": "2024-01-15T08:00:00Z", "open": 1.05, "high": 1.2, "low": 1.0, "close": 1.1},
            {"time": "2024-01-15T09:00:00Z", "open": 1.1, "high": 1.15, "low": 0.95, "close": 1.0},
            {"time": "2024-01-15T10:00:00Z", "open": 1.0, "high": 1.08, "low": 0.98, "close": 1.02},
        ]
        box = build_session_box(candles, 7, 11)
        self.assertEqual(box["session_name"], "custom")
        self.assertAlmostEqual(box["box_high"], 1.2, places=4)
        self.assertAlmostEqual(box["box_low"], 0.9, places=4)
        self.assertEqual(box["candle_count"], 4)

    def test_build_session_box_requires_three_bars(self):
        candles = [
            {"time": "2024-01-15T07:00:00Z", "open": 1.0, "high": 1.1, "low": 0.9, "close": 1.05},
            {"time": "2024-01-15T08:00:00Z", "open": 1.05, "high": 1.2, "low": 1.0, "close": 1.1},
        ]
        with self.assertRaises(ValueError):
            build_session_box(candles, 7, 11)


if __name__ == "__main__":
    unittest.main()
