"""Tests for data/session_filter.py"""

from datetime import datetime, timezone

import pytest

from data.session_filter import (get_active_session, is_trading_allowed,
                                 seconds_to_next_session)


def utc(year, month, day, hour, minute=0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)


class TestGetActiveSession:
    def test_london_open(self):
        assert get_active_session(utc(2026, 6, 15, 8, 0)) == "london"

    def test_london_boundary_start(self):
        assert get_active_session(utc(2026, 6, 15, 7, 0)) == "london"

    def test_london_boundary_end_exclusive(self):
        # 10:00 is exclusive (session closed)
        assert get_active_session(utc(2026, 6, 15, 10, 0)) is None

    def test_newyork_open(self):
        assert get_active_session(utc(2026, 6, 15, 14, 0)) == "newyork"

    def test_newyork_boundary_start(self):
        assert get_active_session(utc(2026, 6, 15, 13, 0)) == "newyork"

    def test_newyork_boundary_end_exclusive(self):
        assert get_active_session(utc(2026, 6, 15, 16, 0)) is None

    def test_off_hours_morning(self):
        assert get_active_session(utc(2026, 6, 15, 6, 59)) is None

    def test_off_hours_midday(self):
        assert get_active_session(utc(2026, 6, 15, 11, 30)) is None

    def test_off_hours_evening(self):
        assert get_active_session(utc(2026, 6, 15, 20, 0)) is None

    def test_saturday_blocked(self):
        # 2026-06-20 is a Saturday
        assert get_active_session(utc(2026, 6, 20, 8, 0)) is None

    def test_sunday_blocked(self):
        # 2026-06-21 is a Sunday
        assert get_active_session(utc(2026, 6, 21, 14, 0)) is None

    def test_friday_allowed(self):
        # 2026-06-19 is a Friday
        assert get_active_session(utc(2026, 6, 19, 8, 0)) == "london"


class TestIsTradingAllowed:
    def test_true_in_session(self):
        assert is_trading_allowed(utc(2026, 6, 15, 9, 0)) is True

    def test_false_off_hours(self):
        assert is_trading_allowed(utc(2026, 6, 15, 12, 0)) is False

    def test_false_weekend(self):
        assert is_trading_allowed(utc(2026, 6, 20, 9, 0)) is False


class TestSecondsToNextSession:
    def test_in_session_returns_zero(self):
        assert seconds_to_next_session(utc(2026, 6, 15, 8, 0)) == 0

    def test_before_london_returns_positive(self):
        secs = seconds_to_next_session(utc(2026, 6, 15, 6, 0))
        assert secs == 3600  # 1 hour until 07:00

    def test_between_sessions(self):
        # 11:00 UTC — next session is NY at 13:00 = 7200 seconds
        secs = seconds_to_next_session(utc(2026, 6, 15, 11, 0))
        assert secs == 7200

    def test_friday_after_ny_waits_until_monday_london(self):
        # Friday 17:00 UTC — next session is Monday London 07:00
        secs = seconds_to_next_session(utc(2026, 6, 19, 17, 0))
        # Friday 17:00 → Monday 07:00 = 2 days + 14 hours = (2*86400) + (14*3600)
        expected = 2 * 86400 + 14 * 3600
        assert secs == expected
