"""Tests for execution/trade_journal.py"""

import json
import pytest
from pathlib import Path
from execution.trade_journal import DemoTradeJournal


def _signal():
    """Minimal signal-like object."""
    from types import SimpleNamespace
    return SimpleNamespace(
        pair="EURUSD", side="long", session="london",
        entry=1.1000, stop_loss=1.0950, take_profit=1.1150,
        strategy_name="ST-A2",
    )


def _order():
    return {"order_id": "SIM-EUR-ABC123", "simulated": True}


class TestDemoTradeJournal:
    def test_log_open_creates_file(self, tmp_path):
        j = DemoTradeJournal(tmp_path / "trades.jsonl")
        j.log_open(_signal(), _order(), 0.02, 0.9)
        assert (tmp_path / "trades.jsonl").exists()

    def test_log_open_fields(self, tmp_path):
        j = DemoTradeJournal(tmp_path / "trades.jsonl")
        j.log_open(_signal(), _order(), 0.02, 0.9)
        r = j.read_all()[0]
        assert r["symbol"]    == "EURUSD"
        assert r["direction"] == "long"
        assert r["entry"]     == pytest.approx(1.1000)
        assert r["stop_loss"] == pytest.approx(1.0950)
        assert r["lot_size"]  == pytest.approx(0.02)
        assert r["spread"]    == pytest.approx(0.9)
        assert r["strategy"]  == "ST-A2"
        assert r["simulated"] is True

    def test_required_fields_present(self, tmp_path):
        j = DemoTradeJournal(tmp_path / "trades.jsonl")
        j.log_open(_signal(), _order(), 0.02, 0.9)
        r = j.read_all()[0]
        for field in ("timestamp", "symbol", "direction", "entry", "stop_loss",
                      "take_profit", "lot_size", "spread", "session", "strategy",
                      "exit", "result_R"):
            assert field in r, f"Missing field: {field}"

    def test_log_close_fields(self, tmp_path):
        j = DemoTradeJournal(tmp_path / "trades.jsonl")
        j.log_close("POS-001", 1.1145, 2.9)
        r = j.read_all()[0]
        assert r["record_type"] == "close"
        assert r["exit"]        == pytest.approx(1.1145)
        assert r["result_R"]    == pytest.approx(2.9)

    def test_summary_counts(self, tmp_path):
        j = DemoTradeJournal(tmp_path / "trades.jsonl")
        j.log_open(_signal(), _order(), 0.02, 0.9)
        j.log_open(_signal(), _order(), 0.02, 0.9)
        j.log_close("A", 1.1145, 2.9)
        j.log_close("B", 1.0960, -1.0)
        s = j.summary()
        assert s["total_opened"] == 2
        assert s["total_closed"] == 2
        assert s["wins"]   == 1
        assert s["losses"] == 1

    def test_summary_empty(self, tmp_path):
        j = DemoTradeJournal(tmp_path / "trades.jsonl")
        s = j.summary()
        assert s["total_opened"] == 0
        assert s["avg_r"] == 0.0

    def test_read_all_empty_no_file(self, tmp_path):
        j = DemoTradeJournal(tmp_path / "no.jsonl")
        assert j.read_all() == []
