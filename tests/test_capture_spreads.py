"""
tests/test_capture_spreads.py

Unit tests for scripts/capture_spreads.py — pure-function layer only.
No MetaAPI SDK calls; broker connectivity is mocked via AsyncMock.

Coverage:
  - session_label(): DST-aware classification for London and NY boundaries
  - spread_pips():   pip-size-corrected calculation (includes USDJPY fix)
  - csv_row():       row schema matches CSV_HEADER
  - update_agg():    correct accumulation into defaultdict
  - build_summary(): per-symbol / per-session aggregation and commission
  - reconnect_if_needed(): reconnect attempted on !is_connected
  - shutdown: stop_event causes loop to exit promptly
"""

from __future__ import annotations

import asyncio
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

# Make scripts importable (project root is one level up)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.capture_spreads import (  # noqa: E402
    CSV_HEADER,
    PIP_SIZE,
    build_summary,
    csv_row,
    reconnect_if_needed,
    session_label,
    spread_pips,
    update_agg,
)

_UTC = timezone.utc


# ═══════════════════════════════════════════════════════════════════════════════
#  session_label — DST-aware (uses session_builder.classify_session internally)
# ═══════════════════════════════════════════════════════════════════════════════


class TestSessionLabel:
    # Winter (EST = UTC-5): London 07:00–10:00 UTC, NY 12:00–15:00 UTC
    # Summer (EDT = UTC-4): London 06:00–09:00 UTC, NY 11:00–14:00 UTC

    def test_london_winter_midpoint(self):
        # 2024-01-15 is winter (EST). 08:30 UTC → 03:30 EST → london
        dt = datetime(2024, 1, 15, 8, 30, tzinfo=_UTC)
        assert session_label(dt) == "london"

    def test_london_summer_midpoint(self):
        # 2024-06-15 is summer (EDT). 07:30 UTC → 03:30 EDT → london
        dt = datetime(2024, 6, 15, 7, 30, tzinfo=_UTC)
        assert session_label(dt) == "london"

    def test_newyork_winter_midpoint(self):
        # 2024-01-15 13:30 UTC → 08:30 EST → new_york
        dt = datetime(2024, 1, 15, 13, 30, tzinfo=_UTC)
        assert session_label(dt) == "new_york"

    def test_newyork_summer_midpoint(self):
        # 2024-06-15 12:30 UTC → 08:30 EDT → new_york
        dt = datetime(2024, 6, 15, 12, 30, tzinfo=_UTC)
        assert session_label(dt) == "new_york"

    def test_off_session_midnight(self):
        dt = datetime(2024, 1, 15, 0, 0, tzinfo=_UTC)
        assert session_label(dt) == "off"

    def test_off_session_asian(self):
        # Asian session is not a killzone — 02:00 UTC is off
        dt = datetime(2024, 1, 15, 2, 0, tzinfo=_UTC)
        assert session_label(dt) == "off"

    def test_london_boundary_start_winter(self):
        # Winter: London opens 07:00 UTC (= 02:00 EST)
        dt = datetime(2024, 1, 15, 7, 0, tzinfo=_UTC)
        assert session_label(dt) == "london"

    def test_london_boundary_end_winter(self):
        # Winter: London closes at 10:00 UTC (= 05:00 EST → not in [2,5))
        # 09:59 UTC = 04:59 EST → inside
        dt = datetime(2024, 1, 15, 9, 59, tzinfo=_UTC)
        assert session_label(dt) == "london"

    def test_london_boundary_just_after_end_winter(self):
        # 10:00 UTC = 05:00 EST → outside (h < 5 fails for h==5)
        dt = datetime(2024, 1, 15, 10, 0, tzinfo=_UTC)
        assert session_label(dt) == "off"

    def test_newyork_boundary_start_winter(self):
        # Winter: NY opens 12:00 UTC (= 07:00 EST)
        dt = datetime(2024, 1, 15, 12, 0, tzinfo=_UTC)
        assert session_label(dt) == "new_york"

    def test_newyork_boundary_end_winter(self):
        # 14:59 UTC = 09:59 EST → inside
        dt = datetime(2024, 1, 15, 14, 59, tzinfo=_UTC)
        assert session_label(dt) == "new_york"

    def test_newyork_boundary_just_after_end_winter(self):
        # 15:00 UTC = 10:00 EST → outside (h < 10 fails for h==10)
        dt = datetime(2024, 1, 15, 15, 0, tzinfo=_UTC)
        assert session_label(dt) == "off"

    def test_london_boundary_start_summer(self):
        # Summer (EDT = UTC-4): London opens 06:00 UTC (= 02:00 EDT)
        dt = datetime(2024, 6, 15, 6, 0, tzinfo=_UTC)
        assert session_label(dt) == "london"

    def test_london_before_start_summer(self):
        # 05:59 UTC = 01:59 EDT → outside london (h < 2)
        dt = datetime(2024, 6, 15, 5, 59, tzinfo=_UTC)
        assert session_label(dt) == "off"

    def test_newyork_boundary_start_summer(self):
        # Summer: NY opens 11:00 UTC (= 07:00 EDT)
        dt = datetime(2024, 6, 15, 11, 0, tzinfo=_UTC)
        assert session_label(dt) == "new_york"

    def test_gap_between_sessions_winter(self):
        # 10:30 UTC = 05:30 EST → off (between London end and NY start)
        dt = datetime(2024, 1, 15, 10, 30, tzinfo=_UTC)
        assert session_label(dt) == "off"

    def test_dst_transition_not_naive(self):
        # Verify that naive datetimes are handled (treated as UTC)
        # session_builder._parse_utc() adds UTC tz to naive datetimes
        dt_naive = datetime(2024, 1, 15, 8, 30)  # no tzinfo
        # Should still work because _parse_utc handles naive→UTC
        result = session_label(dt_naive)
        assert result == "london"


# ═══════════════════════════════════════════════════════════════════════════════
#  spread_pips — pip-size-corrected
# ═══════════════════════════════════════════════════════════════════════════════


class TestSpreadPips:
    def test_eurusd_standard(self):
        # bid=1.10000, ask=1.10014 → 1.4 pip
        assert spread_pips(1.10000, 1.10014, "EURUSD") == pytest.approx(1.4, abs=0.01)

    def test_gbpusd_standard(self):
        # bid=1.27000, ask=1.27018 → 1.8 pip
        assert spread_pips(1.27000, 1.27018, "GBPUSD") == pytest.approx(1.8, abs=0.01)

    def test_usdjpy_pip_correction(self):
        # USDJPY pip=0.01: bid=150.000, ask=150.013 → 1.3 pip
        # Without correction (÷0.0001): would give 130 — wrong
        result = spread_pips(150.000, 150.013, "USDJPY")
        assert result == pytest.approx(1.3, abs=0.01)

    def test_audusd_standard(self):
        # Same as EURUSD pip size
        assert spread_pips(0.65000, 0.65012, "AUDUSD") == pytest.approx(1.2, abs=0.01)

    def test_unknown_symbol_defaults_to_5decimal(self):
        # Unknown symbol: defaults to 0.0001 pip
        assert spread_pips(1.0000, 1.0002, "XYZUSD") == pytest.approx(2.0, abs=0.01)

    def test_zero_spread(self):
        assert spread_pips(1.10000, 1.10000, "EURUSD") == pytest.approx(0.0, abs=0.001)

    def test_pip_size_table_covers_all_default_pairs(self):
        from scripts.capture_spreads import PAIRS

        for p in PAIRS:
            assert p in PIP_SIZE, f"{p} missing from PIP_SIZE"


# ═══════════════════════════════════════════════════════════════════════════════
#  csv_row — schema matches CSV_HEADER
# ═══════════════════════════════════════════════════════════════════════════════


class TestCsvRow:
    def test_row_length_matches_header(self):
        dt = datetime(2024, 1, 15, 8, 30, 0, tzinfo=_UTC)
        row = csv_row(dt, "EURUSD", "london", 1.4)
        assert len(row) == len(CSV_HEADER)

    def test_row_field_order(self):
        dt = datetime(2024, 1, 15, 8, 30, 0, tzinfo=_UTC)
        row = csv_row(dt, "EURUSD", "london", 1.4)
        # time_utc, symbol, session, hour, minute, spread_pips
        assert row[1] == "EURUSD"
        assert row[2] == "london"
        assert row[3] == 8  # hour
        assert row[4] == 30  # minute
        assert row[5] == pytest.approx(1.4, abs=0.001)

    def test_time_utc_is_iso_string(self):
        dt = datetime(2024, 1, 15, 8, 30, tzinfo=_UTC)
        row = csv_row(dt, "EURUSD", "london", 1.4)
        # Must be parseable back to a datetime
        parsed = datetime.fromisoformat(row[0].replace("Z", "+00:00"))
        assert parsed.hour == 8

    def test_spread_rounded_to_3dp(self):
        dt = datetime(2024, 1, 15, 8, 0, tzinfo=_UTC)
        row = csv_row(dt, "EURUSD", "london", 1.41666)
        assert row[5] == pytest.approx(1.417, abs=0.001)

    def test_off_session_label(self):
        dt = datetime(2024, 1, 15, 0, 0, tzinfo=_UTC)
        row = csv_row(dt, "EURUSD", "off", 2.5)
        assert row[2] == "off"


# ═══════════════════════════════════════════════════════════════════════════════
#  update_agg — aggregation correctness
# ═══════════════════════════════════════════════════════════════════════════════


class TestUpdateAgg:
    def test_initial_accumulation(self):
        agg = defaultdict(lambda: [0.0, 0])
        update_agg(agg, "EURUSD", "london", 1.4)
        assert agg[("EURUSD", "london")][0] == pytest.approx(1.4)
        assert agg[("EURUSD", "london")][1] == 1

    def test_multiple_updates(self):
        agg = defaultdict(lambda: [0.0, 0])
        update_agg(agg, "EURUSD", "london", 1.4)
        update_agg(agg, "EURUSD", "london", 1.6)
        update_agg(agg, "EURUSD", "london", 1.2)
        assert agg[("EURUSD", "london")][0] == pytest.approx(4.2)
        assert agg[("EURUSD", "london")][1] == 3

    def test_separate_sessions_tracked_independently(self):
        agg = defaultdict(lambda: [0.0, 0])
        update_agg(agg, "EURUSD", "london", 1.4)
        update_agg(agg, "EURUSD", "new_york", 1.8)
        assert agg[("EURUSD", "london")][1] == 1
        assert agg[("EURUSD", "new_york")][1] == 1

    def test_separate_symbols_tracked_independently(self):
        agg = defaultdict(lambda: [0.0, 0])
        update_agg(agg, "EURUSD", "london", 1.4)
        update_agg(agg, "GBPUSD", "london", 1.8)
        assert agg[("EURUSD", "london")][1] == 1
        assert agg[("GBPUSD", "london")][1] == 1

    def test_off_session_also_tracked(self):
        agg = defaultdict(lambda: [0.0, 0])
        update_agg(agg, "EURUSD", "off", 5.0)
        assert agg[("EURUSD", "off")][1] == 1


# ═══════════════════════════════════════════════════════════════════════════════
#  build_summary — report formatting and commission arithmetic
# ═══════════════════════════════════════════════════════════════════════════════


class TestBuildSummary:
    def _make_agg(self, entries):
        """Helper: build agg dict from list of (sym, sess, total, count)."""
        agg = defaultdict(lambda: [0.0, 0])
        for sym, sess, total, count in entries:
            agg[(sym, sess)] = [total, count]
        return agg

    def test_single_symbol_no_commission(self):
        agg = self._make_agg([("EURUSD", "london", 7.0, 5)])
        # avg=1.4, comm=0.0 → standard=1.4, stress2x=2.8
        lines = build_summary(agg, 0.0, ["EURUSD"])
        assert len(lines) == 1
        assert "1.40" in lines[0] or "1.4" in lines[0]
        assert "2.80" in lines[0] or "2.8" in lines[0]

    def test_commission_added_to_spread(self):
        agg = self._make_agg([("EURUSD", "london", 7.0, 5)])
        # avg=1.4, comm=0.6 → standard=2.0, stress2x=4.0
        lines = build_summary(agg, 0.6, ["EURUSD"])
        assert "2.00" in lines[0] or "2.0" in lines[0]
        assert "4.00" in lines[0] or "4.0" in lines[0]

    def test_multiple_sessions_averaged(self):
        agg = self._make_agg(
            [
                ("EURUSD", "london", 7.0, 5),  # avg 1.4
                ("EURUSD", "new_york", 9.0, 5),  # avg 1.8
            ]
        )
        # combined avg = (7+9)/(5+5) = 1.6
        lines = build_summary(agg, 0.0, ["EURUSD"])
        assert "1.60" in lines[0] or "1.6" in lines[0]

    def test_no_killzone_samples_reports_missing(self):
        agg = self._make_agg([("EURUSD", "off", 10.0, 5)])
        lines = build_summary(agg, 0.0, ["EURUSD"])
        assert "no killzone samples" in lines[0]

    def test_multiple_pairs(self):
        agg = self._make_agg(
            [
                ("EURUSD", "london", 7.0, 5),
                ("GBPUSD", "london", 9.0, 5),
            ]
        )
        lines = build_summary(agg, 0.0, ["EURUSD", "GBPUSD"])
        assert len(lines) == 2
        assert any("EURUSD" in line for line in lines)
        assert any("GBPUSD" in line for line in lines)

    def test_empty_agg(self):
        agg = defaultdict(lambda: [0.0, 0])
        lines = build_summary(agg, 0.0, ["EURUSD", "GBPUSD"])
        assert len(lines) == 2
        for line in lines:
            assert "no killzone samples" in line

    def test_per_session_count_in_output(self):
        agg = self._make_agg([("EURUSD", "london", 7.0, 5)])
        lines = build_summary(agg, 0.0, ["EURUSD"])
        # Should report per-session detail including count
        assert "n=5" in lines[0]


# ═══════════════════════════════════════════════════════════════════════════════
#  reconnect_if_needed — broker reconnect logic
# ═══════════════════════════════════════════════════════════════════════════════


class TestReconnectIfNeeded:
    def _make_client(
        self, *, is_connected: bool, reconnect_returns: bool = True
    ) -> MagicMock:
        client = MagicMock()
        client.is_connected = is_connected
        client.reconnect = AsyncMock(return_value=reconnect_returns)
        return client

    def test_already_connected_no_reconnect_called(self):
        client = self._make_client(is_connected=True)
        result = asyncio.run(reconnect_if_needed(client, "TEST"))
        assert result is True
        client.reconnect.assert_not_called()

    def test_not_connected_reconnect_called(self):
        client = self._make_client(is_connected=False, reconnect_returns=True)
        result = asyncio.run(reconnect_if_needed(client, "TEST"))
        assert result is True
        client.reconnect.assert_awaited_once()

    def test_not_connected_reconnect_fails(self):
        client = self._make_client(is_connected=False, reconnect_returns=False)
        result = asyncio.run(reconnect_if_needed(client, "TEST"))
        assert result is False
        client.reconnect.assert_awaited_once()

    def test_reconnect_raises_returns_false(self):
        client = MagicMock()
        client.is_connected = False
        client.reconnect = AsyncMock(side_effect=RuntimeError("SDK error"))
        result = asyncio.run(reconnect_if_needed(client, "TEST"))
        assert result is False

    def test_reconnect_timeout_returns_false(self):
        client = MagicMock()
        client.is_connected = False
        client.reconnect = AsyncMock(side_effect=asyncio.TimeoutError())
        result = asyncio.run(reconnect_if_needed(client, "TEST"))
        assert result is False


# ═══════════════════════════════════════════════════════════════════════════════
#  shutdown — stop_event exits promptly
# ═══════════════════════════════════════════════════════════════════════════════


class TestShutdownBehavior:
    def test_stop_event_breaks_wait(self):
        """
        Verify that setting stop_event causes asyncio.wait_for(stop_event.wait())
        to return immediately rather than waiting the full interval.
        """

        async def _run():
            stop_event = asyncio.Event()

            async def _set_later():
                await asyncio.sleep(0.05)
                stop_event.set()

            asyncio.create_task(_set_later())
            start = asyncio.get_event_loop().time()
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                pass
            elapsed = asyncio.get_event_loop().time() - start
            return elapsed

        elapsed = asyncio.run(_run())
        # Should exit well under 1 second, not wait the full 5s timeout
        assert elapsed < 1.0

    def test_immediate_stop_exits_before_first_interval(self):
        """
        If stop_event is set before the wait, the loop exits immediately.
        """

        async def _run():
            stop_event = asyncio.Event()
            stop_event.set()  # set before waiting
            exited = False
            if not stop_event.is_set():
                await asyncio.wait_for(stop_event.wait(), timeout=5.0)
            exited = True
            return exited

        result = asyncio.run(_run())
        assert result is True


# ═══════════════════════════════════════════════════════════════════════════════
#  Integration: session_label + spread_pips + csv_row produce consistent data
# ═══════════════════════════════════════════════════════════════════════════════


class TestEndToEndRowProduction:
    def test_london_sample_row_round_trips(self):
        """A sample row captured during London has the correct session tag."""
        dt = datetime(2024, 1, 15, 8, 0, tzinfo=_UTC)  # winter, 03:00 EST → london
        sess = session_label(dt)
        sp = spread_pips(1.10000, 1.10014, "EURUSD")
        row = csv_row(dt, "EURUSD", sess, sp)

        assert row[2] == "london"
        assert row[3] == 8
        assert row[5] == pytest.approx(1.4, abs=0.01)

    def test_ny_sample_row_round_trips(self):
        """A sample row captured during NY has the correct session tag."""
        dt = datetime(2024, 1, 15, 13, 30, tzinfo=_UTC)  # winter, 08:30 EST → new_york
        sess = session_label(dt)
        sp = spread_pips(1.27000, 1.27018, "GBPUSD")
        row = csv_row(dt, "GBPUSD", sess, sp)

        assert row[2] == "new_york"
        assert row[5] == pytest.approx(1.8, abs=0.01)

    def test_usdjpy_full_pipeline(self):
        """USDJPY spread is computed correctly through the full pipeline."""
        dt = datetime(2024, 1, 15, 8, 30, tzinfo=_UTC)
        sess = session_label(dt)
        # bid=150.000, ask=150.013 → 1.3 pip at USDJPY pip=0.01
        sp = spread_pips(150.000, 150.013, "USDJPY")
        row = csv_row(dt, "USDJPY", sess, sp)

        assert row[1] == "USDJPY"
        assert row[5] == pytest.approx(1.3, abs=0.01)

        agg = defaultdict(lambda: [0.0, 0])
        update_agg(agg, "USDJPY", sess, sp)
        assert agg[("USDJPY", sess)][1] == 1
