"""Tests for adaptive/simulation/paper_execution.py"""

import pytest
from adaptive.strategies import AdaptiveSignal
from adaptive.simulation.paper_execution import PaperExecution


def _signal(direction: str = "LONG", entry: float = 1.1000,
            sl: float = 1.0950, tp: float = 1.1150) -> AdaptiveSignal:
    return AdaptiveSignal(
        strategy    = "smc_session",
        pair        = "EURUSD",
        direction   = direction,
        entry_price = entry,
        sl_price    = sl,
        tp_price    = tp,
        session     = "london",
        timestamp   = "2026-06-24T07:30:00+00:00",
        reason      = "test",
    )


class TestPaperExecution:
    def test_open_trade_returns_id(self):
        pe = PaperExecution()
        tid = pe.open_trade(_signal())
        assert isinstance(tid, str)
        assert len(tid) > 0

    def test_open_trade_appears_in_get_open(self):
        pe = PaperExecution()
        tid = pe.open_trade(_signal())
        ids = [t["trade_id"] for t in pe.get_open()]
        assert tid in ids

    def test_update_returns_none_when_not_hit(self):
        pe = PaperExecution()
        tid = pe.open_trade(_signal())
        result = pe.update(tid, 1.1010)   # between SL and TP
        assert result is None

    def test_tp_hit_closes_trade(self):
        pe = PaperExecution()
        tid = pe.open_trade(_signal(direction="LONG", entry=1.1000, sl=1.0950, tp=1.1150))
        closed = pe.update(tid, 1.1160)   # above TP
        assert closed is not None
        assert closed["status"] == "tp"
        assert closed["pnl_r"] > 0

    def test_sl_hit_closes_trade(self):
        pe = PaperExecution()
        tid = pe.open_trade(_signal(direction="LONG", entry=1.1000, sl=1.0950, tp=1.1150))
        closed = pe.update(tid, 1.0940)   # below SL
        assert closed is not None
        assert closed["status"] == "sl"
        assert closed["pnl_r"] < 0

    def test_short_tp_hit(self):
        pe = PaperExecution()
        sig = _signal(direction="SHORT", entry=1.1000, sl=1.1050, tp=1.0850)
        tid = pe.open_trade(sig)
        closed = pe.update(tid, 1.0840)   # below TP for SHORT
        assert closed["status"] == "tp"
        assert closed["pnl_r"] > 0

    def test_closed_trade_removed_from_open(self):
        pe = PaperExecution()
        tid = pe.open_trade(_signal())
        pe.update(tid, 1.1160)
        open_ids = [t["trade_id"] for t in pe.get_open()]
        assert tid not in open_ids

    def test_closed_trade_in_get_closed(self):
        pe = PaperExecution()
        tid = pe.open_trade(_signal())
        pe.update(tid, 1.1160)
        closed_ids = [t["trade_id"] for t in pe.get_closed()]
        assert tid in closed_ids

    def test_close_all_session_end(self):
        pe = PaperExecution()
        pe.open_trade(_signal())
        pe.open_trade(_signal())
        closed = pe.close_all(1.1010, reason="session_end")
        assert len(closed) == 2
        assert pe.get_open() == []

    def test_pnl_r_approx_1r_at_tp(self):
        pe = PaperExecution()
        # entry=1.1000, sl=1.0950 (50 pip risk), tp=1.1050 (50 pip reward = 1R)
        tid = pe.open_trade(_signal(entry=1.1000, sl=1.0950, tp=1.1050))
        closed = pe.update(tid, 1.1055)
        assert closed["pnl_r"] == pytest.approx(1.0, rel=0.05)
