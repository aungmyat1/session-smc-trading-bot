"""Tests for adaptive/journal/trade_journal.py"""

import pytest
from adaptive.strategies import AdaptiveSignal
from adaptive.journal.trade_journal import TradeJournal


def _signal() -> AdaptiveSignal:
    return AdaptiveSignal(
        strategy="london_breakout",
        pair="EURUSD",
        direction="LONG",
        entry_price=1.1000,
        sl_price=1.0950,
        tp_price=1.1150,
        session="london",
        timestamp="2026-06-24T07:30:00+00:00",
        reason="test",
    )


def _router_result(approved: bool = True, score: int = 8) -> dict:
    return {
        "decision": "APPROVED" if approved else "REJECTED",
        "rejection_reason": "" if approved else "SCORE_REJECTED",
        "regime": {"regime": "RANGING"},
        "score_result": {"score": score, "approved": approved},
    }


def _closed_trade() -> dict:
    return {
        "trade_id": "abc12345",
        "pair": "EURUSD",
        "strategy": "london_breakout",
        "direction": "LONG",
        "entry": 1.1000,
        "sl": 1.0950,
        "tp": 1.1150,
        "status": "tp",
        "pnl_r": 1.5,
        "closed_at": "2026-06-24T08:00:00+00:00",
    }


class TestTradeJournal:
    def test_log_signal_creates_file(self, tmp_path):
        j = TradeJournal(tmp_path / "trades.jsonl")
        j.log_signal(_signal(), _router_result())
        assert (tmp_path / "trades.jsonl").exists()

    def test_log_signal_record_type(self, tmp_path):
        j = TradeJournal(tmp_path / "trades.jsonl")
        j.log_signal(_signal(), _router_result())
        records = j.read_all()
        assert len(records) == 1
        assert records[0]["record_type"] == "signal"

    def test_log_signal_fields(self, tmp_path):
        j = TradeJournal(tmp_path / "trades.jsonl")
        j.log_signal(_signal(), _router_result(approved=True, score=8))
        r = j.read_all()[0]
        assert r["symbol"] == "EURUSD"
        assert r["strategy"] == "london_breakout"
        assert r["direction"] == "LONG"
        assert r["score"] == 8
        assert r["decision"] == "APPROVED"

    def test_log_trade_fields(self, tmp_path):
        j = TradeJournal(tmp_path / "trades.jsonl")
        j.log_trade(_closed_trade())
        r = j.read_all()[0]
        assert r["record_type"] == "trade"
        assert r["symbol"] == "EURUSD"
        assert r["result"] == "tp"
        assert r["r_multiple"] == pytest.approx(1.5)

    def test_multiple_records_appended(self, tmp_path):
        j = TradeJournal(tmp_path / "trades.jsonl")
        j.log_signal(_signal(), _router_result())
        j.log_trade(_closed_trade())
        j.log_signal(_signal(), _router_result(approved=False))
        records = j.read_all()
        assert len(records) == 3

    def test_read_all_empty_when_no_file(self, tmp_path):
        j = TradeJournal(tmp_path / "nonexistent.jsonl")
        assert j.read_all() == []

    def test_read_all_skips_corrupt_lines(self, tmp_path):
        path = tmp_path / "trades.jsonl"
        path.write_text('{"valid":true}\nnot json\n{"also":"valid"}\n')
        j = TradeJournal(path)
        records = j.read_all()
        assert len(records) == 2

    def test_required_trade_keys_present(self, tmp_path):
        j = TradeJournal(tmp_path / "trades.jsonl")
        j.log_trade(_closed_trade())
        r = j.read_all()[0]
        for key in (
            "timestamp",
            "symbol",
            "strategy",
            "direction",
            "entry",
            "sl",
            "tp",
            "result",
            "r_multiple",
        ):
            assert key in r, f"Missing: {key}"
