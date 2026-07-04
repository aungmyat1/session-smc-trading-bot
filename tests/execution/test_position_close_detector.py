from __future__ import annotations

from execution.position_close_detector import diff_closed_positions, match_journal_trade


class TestDiffClosedPositions:
    def test_no_change_reports_nothing_closed(self):
        positions = [{"id": "ORD-1", "symbol": "EURUSD"}]
        assert diff_closed_positions(positions, positions) == []

    def test_disappeared_position_is_reported_closed(self):
        previous = [{"id": "ORD-1", "symbol": "EURUSD"}, {"id": "ORD-2", "symbol": "GBPUSD"}]
        current = [{"id": "ORD-2", "symbol": "GBPUSD"}]
        closed = diff_closed_positions(previous, current)
        assert len(closed) == 1
        assert closed[0]["id"] == "ORD-1"

    def test_new_position_is_not_reported_closed(self):
        previous = [{"id": "ORD-1", "symbol": "EURUSD"}]
        current = [{"id": "ORD-1", "symbol": "EURUSD"}, {"id": "ORD-2", "symbol": "GBPUSD"}]
        assert diff_closed_positions(previous, current) == []

    def test_empty_previous_reports_nothing(self):
        assert diff_closed_positions([], [{"id": "ORD-1", "symbol": "EURUSD"}]) == []

    def test_position_missing_id_is_ignored(self):
        previous = [{"symbol": "EURUSD"}]
        assert diff_closed_positions(previous, []) == []


class TestMatchJournalTrade:
    def test_matches_by_symbol_and_broker_order_id(self):
        closed_position = {"id": "ORD-1", "symbol": "EURUSD"}
        open_trades = [
            {"id": 5, "symbol": "EURUSD", "broker_order_id": "ORD-1"},
            {"id": 6, "symbol": "GBPUSD", "broker_order_id": "ORD-2"},
        ]
        matched = match_journal_trade(closed_position, open_trades)
        assert matched is not None
        assert matched["id"] == 5

    def test_no_match_returns_none(self):
        closed_position = {"id": "ORD-9", "symbol": "EURUSD"}
        open_trades = [{"id": 5, "symbol": "EURUSD", "broker_order_id": "ORD-1"}]
        assert match_journal_trade(closed_position, open_trades) is None

    def test_symbol_mismatch_is_not_matched(self):
        closed_position = {"id": "ORD-1", "symbol": "GBPUSD"}
        open_trades = [{"id": 5, "symbol": "EURUSD", "broker_order_id": "ORD-1"}]
        assert match_journal_trade(closed_position, open_trades) is None

    def test_missing_position_id_returns_none(self):
        closed_position = {"symbol": "EURUSD"}
        open_trades = [{"id": 5, "symbol": "EURUSD", "broker_order_id": ""}]
        assert match_journal_trade(closed_position, open_trades) is None
