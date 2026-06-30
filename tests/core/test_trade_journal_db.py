"""Tests: SQLite trade journal — record, update, query, analytics."""

from datetime import datetime, timezone

import pytest

from core.signal import Signal
from core.trade_journal_db import TradeJournalDB


def _sig(symbol="EURUSD", action="BUY") -> Signal:
    return Signal(
        timestamp=datetime.now(timezone.utc).isoformat(),
        strategy_name="ST-A2",
        symbol=symbol,
        action=action,
        entry_price=1.10000,
        stop_loss=1.09500,
        take_profit=1.11000,
        risk_percent=0.25,
        confidence=0.90,
        metadata={"session": "london", "risk_pips": 5.0},
    )


@pytest.fixture
def db(tmp_path):
    return TradeJournalDB(tmp_path / "test_journal.db")


class TestRecordSignal:
    def test_returns_positive_id(self, db):
        trade_id = db.record_signal(_sig(), router_result="PASS",
                                    breaker_result="PASS",
                                    portfolio_result="PASS",
                                    execution_result="OPEN")
        assert trade_id > 0

    def test_record_stored_in_db(self, db):
        tid = db.record_signal(_sig(), execution_result="OPEN")
        t   = db.get_trade(tid)
        assert t is not None
        assert t["symbol"]       == "EURUSD"
        assert t["direction"]    == "long"
        assert t["entry_price"]  == 1.10
        assert t["stop_loss"]    == 1.095
        assert t["take_profit"]  == 1.11
        assert t["risk_percentage"] == 0.25
        assert t["strategy_name"]   == "ST-A2"

    def test_sell_direction_mapped(self, db):
        tid = db.record_signal(_sig(action="SELL"), execution_result="OPEN")
        t   = db.get_trade(tid)
        assert t["direction"] == "short"

    def test_pipeline_results_stored(self, db):
        tid = db.record_signal(
            _sig(),
            router_result="PASS",
            breaker_result="PASS",
            portfolio_result="BLOCKED",
            execution_result="SKIPPED",
        )
        t = db.get_trade(tid)
        assert t["router_result"]    == "PASS"
        assert t["portfolio_result"] == "BLOCKED"
        assert t["execution_result"] == "SKIPPED"
        assert t["status"]           == "BLOCKED"

    def test_open_status_on_open_result(self, db):
        tid = db.record_signal(_sig(), execution_result="OPEN")
        t   = db.get_trade(tid)
        assert t["status"] == "OPEN"

    def test_shadow_status_on_shadow_result(self, db):
        tid = db.record_signal(_sig(), execution_result="SHADOW")
        t   = db.get_trade(tid)
        assert t["status"] == "OPEN"

    def test_broker_order_id_stored(self, db):
        tid = db.record_signal(_sig(), broker_order_id="ORD-123", execution_result="OPEN")
        t   = db.get_trade(tid)
        assert t["broker_order_id"] == "ORD-123"

    def test_position_size_stored(self, db):
        tid = db.record_signal(_sig(), position_size=0.05, execution_result="OPEN")
        t   = db.get_trade(tid)
        assert t["position_size"] == pytest.approx(0.05)


class TestUpdateClose:
    def test_close_updates_status(self, db):
        tid = db.record_signal(_sig(), execution_result="OPEN")
        db.update_close(tid, close_price=1.115, profit_loss=25.0, r_multiple=2.5)
        t = db.get_trade(tid)
        assert t["status"]      == "CLOSED"
        assert t["close_price"] == 1.115
        assert t["r_multiple"]  == pytest.approx(2.5, abs=0.001)
        assert t["profit_loss"] == pytest.approx(25.0)

    def test_reason_for_exit_stored(self, db):
        tid = db.record_signal(_sig(), execution_result="OPEN")
        db.update_close(tid, close_price=1.09, profit_loss=-12.0, r_multiple=-1.0,
                        reason_for_exit="sl_hit")
        t = db.get_trade(tid)
        assert t["reason_for_exit"] == "sl_hit"

    def test_entry_price_update_on_close(self, db):
        tid = db.record_signal(_sig(), execution_result="OPEN")
        db.update_close(tid, close_price=1.11, profit_loss=10.0, r_multiple=1.0,
                        entry_price=1.1002)
        t = db.get_trade(tid)
        assert t["entry_price"] == pytest.approx(1.1002)


class TestQueries:
    def test_get_open_trades(self, db):
        t1 = db.record_signal(_sig("EURUSD"), execution_result="OPEN")
        t2 = db.record_signal(_sig("XAUUSD"), execution_result="OPEN")
        db.update_close(t1, 1.11, 10.0, 1.0)

        open_trades = db.get_open_trades()
        ids = [t["id"] for t in open_trades]
        assert t2 in ids
        assert t1 not in ids

    def test_get_all_trades(self, db):
        db.record_signal(_sig(), execution_result="OPEN")
        db.record_signal(_sig(), execution_result="BLOCKED")
        all_t = db.get_all_trades()
        assert len(all_t) == 2

    def test_get_trades_by_symbol(self, db):
        db.record_signal(_sig("EURUSD"), execution_result="OPEN")
        db.record_signal(_sig("XAUUSD"), execution_result="OPEN")
        eur = db.get_trades_by_symbol("EURUSD")
        assert len(eur) == 1
        assert eur[0]["symbol"] == "EURUSD"

    def test_get_trade_none_for_unknown_id(self, db):
        assert db.get_trade(99999) is None


class TestSummary:
    def _make_closed(self, db, r: float) -> None:
        tid = db.record_signal(_sig(), execution_result="OPEN")
        db.update_close(tid, 1.11 if r > 0 else 1.09,
                        profit_loss=r * 10, r_multiple=r)

    def test_empty_summary(self, db):
        s = db.summary()
        assert s["total"] == 0
        assert s["wins"]  == 0
        assert s["losses"] == 0

    def test_win_loss_counts(self, db):
        self._make_closed(db, 2.0)
        self._make_closed(db, 2.0)
        self._make_closed(db, -1.0)
        s = db.summary()
        assert s["wins"]   == 2
        assert s["losses"] == 1
        assert s["closed"] == 3

    def test_avg_r_calculation(self, db):
        self._make_closed(db, 2.0)
        self._make_closed(db, -1.0)
        s = db.summary()
        assert s["avg_r"] == pytest.approx(0.5, abs=0.01)

    def test_profit_factor_wins_over_losses(self, db):
        self._make_closed(db, 4.0)
        self._make_closed(db, -1.0)
        s = db.summary()
        assert s["profit_factor"] == pytest.approx(4.0, abs=0.01)

    def test_win_rate_pct(self, db):
        self._make_closed(db, 2.0)
        self._make_closed(db, 2.0)
        self._make_closed(db, -1.0)
        s = db.summary()
        assert s["win_rate_pct"] == pytest.approx(66.7, abs=0.2)

    def test_blocked_counted_separately(self, db):
        db.record_signal(_sig(), execution_result="BLOCKED")
        db.record_signal(_sig(), execution_result="OPEN")
        s = db.summary()
        assert s["blocked"] == 1
        assert s["open"]    == 1
        assert s["total"]   == 2


class TestXAUUSD:
    def test_xauusd_signal_stored(self, db):
        sig = Signal(
            timestamp=datetime.now(timezone.utc).isoformat(),
            strategy_name="ST-A2",
            symbol="XAUUSD",
            action="BUY",
            entry_price=2340.00,
            stop_loss=2330.00,
            take_profit=2380.00,
            risk_percent=0.25,
            confidence=0.85,
            metadata={"session": "london", "risk_pips": 100.0},
        )
        tid = db.record_signal(sig, execution_result="OPEN", position_size=0.01)
        t   = db.get_trade(tid)
        assert t["symbol"]      == "XAUUSD"
        assert t["entry_price"] == pytest.approx(2340.0)
        assert t["stop_loss"]   == pytest.approx(2330.0)
