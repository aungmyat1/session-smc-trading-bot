"""Tests for execution/trade_logger.py — structured JSONL event log."""

import json
from pathlib import Path

import pytest

from execution.trade_logger import _VALID_EVENTS, TradeLogger


@pytest.fixture
def log_file(tmp_path) -> Path:
    return tmp_path / "test_trades.jsonl"


@pytest.fixture
def tl(log_file) -> TradeLogger:
    return TradeLogger(log_file)


# ── Category 1: File creation and append ─────────────────────────────────────


class TestFileCreation:
    def test_creates_parent_directory(self, tmp_path):
        deep = tmp_path / "a" / "b" / "c" / "trades.jsonl"
        tl = TradeLogger(deep)
        tl.error("BOT", "test")
        assert deep.exists()

    def test_appends_not_overwrites(self, tl, log_file):
        tl.error("BOT", "first")
        tl.error("BOT", "second")
        lines = log_file.read_text().strip().splitlines()
        assert len(lines) == 2

    def test_read_all_empty_when_no_file(self, tmp_path):
        tl = TradeLogger(tmp_path / "missing.jsonl")
        assert tl.read_all() == []

    def test_read_all_returns_list_of_dicts(self, tl):
        tl.error("BOT", "x")
        events = tl.read_all()
        assert isinstance(events, list)
        assert isinstance(events[0], dict)


# ── Category 2: All six event types ──────────────────────────────────────────


class TestEventTypes:
    def test_signal_created(self, tl):
        tl.signal_created("EURUSD", "london", "long", 1.07, 1.06, 1.09, 10.0, "sweep")
        ev = tl.read_all()[0]
        assert ev["event"] == "SIGNAL_CREATED"
        assert ev["symbol"] == "EURUSD"
        assert ev["session"] == "london"
        assert ev["side"] == "long"
        assert ev["sl_pips"] == 10.0

    def test_order_submitted(self, tl):
        tl.order_submitted(
            "EURUSD", "london", "long", 0.01, 1.06, 1.09, 0.01, 1000.0, 1.0
        )
        ev = tl.read_all()[0]
        assert ev["event"] == "ORDER_SUBMITTED"
        assert ev["lots"] == 0.01
        assert ev["equity"] == 1000.0

    def test_order_filled(self, tl):
        tl.order_filled("EURUSD", "ord-123", 1.07050, 0.01, 1.06, 1.09, dry_run=True)
        ev = tl.read_all()[0]
        assert ev["event"] == "ORDER_FILLED"
        assert ev["order_id"] == "ord-123"
        assert ev["dry_run"] is True

    def test_order_rejected(self, tl):
        tl.order_rejected("EURUSD", "MAX_OPEN_TRADES:1/1", "long")
        ev = tl.read_all()[0]
        assert ev["event"] == "ORDER_REJECTED"
        assert "MAX_OPEN_TRADES" in ev["reason"]
        assert ev["side"] == "long"

    def test_position_closed(self, tl):
        tl.position_closed("EURUSD", "pos-99", 4.0, "TP1")
        ev = tl.read_all()[0]
        assert ev["event"] == "POSITION_CLOSED"
        assert ev["result_r"] == 4.0
        assert ev["exit_reason"] == "TP1"

    def test_error(self, tl):
        tl.error("GBPUSD", "connection timeout", "scan_pair")
        ev = tl.read_all()[0]
        assert ev["event"] == "ERROR"
        assert ev["error"] == "connection timeout"
        assert ev["context"] == "scan_pair"


# ── Category 3: Record format ─────────────────────────────────────────────────


class TestRecordFormat:
    def test_ts_field_is_iso_format(self, tl):
        tl.error("BOT", "test")
        ev = tl.read_all()[0]
        # ISO 8601 — must parse without raising
        from datetime import datetime

        datetime.fromisoformat(ev["ts"].replace("Z", "+00:00"))

    def test_each_line_is_valid_json(self, tl, log_file):
        tl.signal_created("EURUSD", "london", "long", 1.07, 1.06, 1.09, 10.0)
        tl.order_rejected("EURUSD", "reason", "long")
        for line in log_file.read_text().strip().splitlines():
            json.loads(line)  # must not raise

    def test_event_field_in_every_record(self, tl):
        tl.signal_created("EURUSD", "london", "long", 1.07, 1.06, 1.09, 10.0)
        tl.order_submitted(
            "EURUSD", "london", "long", 0.01, 1.06, 1.09, 0.01, 1000.0, 1.0
        )
        tl.order_filled("EURUSD", "DRY_RUN", 0.0, 0.01, 1.06, 1.09)
        tl.order_rejected("EURUSD", "reason")
        tl.position_closed("EURUSD", "pos-1", -1.0, "SL")
        tl.error("EURUSD", "boom")
        for ev in tl.read_all():
            assert "event" in ev
            assert ev["event"] in _VALID_EVENTS


# ── Category 4: Validation ────────────────────────────────────────────────────


class TestValidation:
    def test_unknown_event_raises(self, tl):
        with pytest.raises(ValueError, match="Unknown event"):
            tl._write("MADE_UP_EVENT", {"symbol": "EURUSD"})

    def test_multiple_events_ordered(self, tl):
        tl.signal_created("EURUSD", "london", "long", 1.07, 1.06, 1.09, 10.0)
        tl.order_submitted(
            "EURUSD", "london", "long", 0.01, 1.06, 1.09, 0.01, 1000.0, 1.0
        )
        tl.order_filled("EURUSD", "DRY_RUN", 0.0, 0.01, 1.06, 1.09)
        events = tl.read_all()
        assert events[0]["event"] == "SIGNAL_CREATED"
        assert events[1]["event"] == "ORDER_SUBMITTED"
        assert events[2]["event"] == "ORDER_FILLED"
