"""
Verifies the real trade-close feedback loop wired into scripts/run_st_a2_demo.py's
`_process_closed_positions()` — the fix for SYSTEM2_MASTER_PLAN.md's Risk Engine /
Position Management findings (record_result()/record_close() were previously dead
code, never called from a real close).
"""

from __future__ import annotations

import pytest

import scripts.run_st_a2_demo as runner
from core.circuit_breaker import CircuitBreaker
from execution.demo_risk_manager import new_state


class _FakeExecutor:
    def __init__(self, balance: float = 10_000.0) -> None:
        self._balance = balance

    async def get_account_info(self):
        return {"balance": self._balance}


class _FakeJournalDB:
    def __init__(self, open_trades=None) -> None:
        self._open_trades = open_trades or []
        self.closes: list[dict] = []

    def get_open_trades(self):
        return self._open_trades

    def update_close(self, trade_id, close_price, profit_loss, r_multiple, reason_for_exit):
        self.closes.append(
            {
                "trade_id": trade_id,
                "close_price": close_price,
                "profit_loss": profit_loss,
                "r_multiple": r_multiple,
                "reason_for_exit": reason_for_exit,
            }
        )


class _FakePortfolioManager:
    def __init__(self) -> None:
        self.closed: list[tuple[str, float]] = []

    def record_close(self, symbol, pnl_pct=0.0):
        self.closed.append((symbol, pnl_pct))


class _FakeTelegram:
    def __init__(self) -> None:
        self.trade_closes: list[dict] = []
        self.mismatches: list[str] = []

    async def send_trade_close(self, **kwargs):
        self.trade_closes.append(kwargs)

    async def send_reconciliation_mismatch(self, summary):
        self.mismatches.append(summary)


@pytest.fixture()
def fakes(monkeypatch):
    fake_journal = _FakeJournalDB()
    fake_portmgr = _FakePortfolioManager()
    monkeypatch.setattr(runner, "_journal_db", fake_journal)
    monkeypatch.setattr(runner, "_portmgr", fake_portmgr)
    monkeypatch.setattr(runner, "_breaker", CircuitBreaker())
    return fake_journal, fake_portmgr


@pytest.mark.asyncio
async def test_no_positions_disappearing_is_a_noop(fakes):
    fake_journal, fake_portmgr = fakes
    risk_state = new_state()
    risk_state["_last_positions"] = [{"id": "ORD-1", "symbol": "EURUSD", "profit": 5.0}]

    result = await runner._process_closed_positions(
        [{"id": "ORD-1", "symbol": "EURUSD", "profit": 5.0}], risk_state, _FakeExecutor(), None,
    )

    assert result["trades_today"] == 0
    assert fake_journal.closes == []
    assert fake_portmgr.closed == []


@pytest.mark.asyncio
async def test_matched_close_updates_journal_risk_and_portfolio(fakes):
    fake_journal, fake_portmgr = fakes
    fake_journal._open_trades = [
        {"id": 42, "symbol": "EURUSD", "broker_order_id": "ORD-1", "strategy_name": "ST-A2",
         "risk_percentage": 0.0025, "direction": "long", "entry_price": 1.1000},
    ]
    risk_state = new_state()
    risk_state["_last_positions"] = [
        {"id": "ORD-1", "symbol": "EURUSD", "profit": -25.0, "current_price": 1.0980}
    ]
    telegram = _FakeTelegram()

    result = await runner._process_closed_positions([], risk_state, _FakeExecutor(balance=10_000.0), telegram)

    assert fake_journal.closes[0]["trade_id"] == 42
    assert fake_journal.closes[0]["profit_loss"] == -25.0
    assert fake_journal.closes[0]["close_price"] == 1.0980
    assert fake_portmgr.closed == [("EURUSD", pytest.approx(-0.0025))]
    assert result["trades_today"] == 1
    assert result["consecutive_losses"] == 1
    assert result["daily_loss_pct"] == pytest.approx(0.0025)
    assert telegram.trade_closes[0]["symbol"] == "EURUSD"
    assert result["_last_positions"] == []
    assert runner._breaker.status()["ST-A2"]["consecutive_losses"] == 1


@pytest.mark.asyncio
async def test_winning_close_resets_consecutive_losses(fakes):
    fake_journal, fake_portmgr = fakes
    fake_journal._open_trades = [
        {"id": 7, "symbol": "GBPUSD", "broker_order_id": "ORD-7",
         "risk_percentage": 0.0025, "direction": "short", "entry_price": 1.25},
    ]
    risk_state = new_state()
    risk_state["consecutive_losses"] = 2
    risk_state["_last_positions"] = [
        {"id": "ORD-7", "symbol": "GBPUSD", "profit": 40.0, "current_price": 1.2450}
    ]

    result = await runner._process_closed_positions([], risk_state, _FakeExecutor(), None)

    assert result["consecutive_losses"] == 0
    assert fake_portmgr.closed == [("GBPUSD", pytest.approx(0.004))]


@pytest.mark.asyncio
async def test_unmatched_close_alerts_and_does_not_update_risk_state(fakes):
    fake_journal, fake_portmgr = fakes
    fake_journal._open_trades = []
    risk_state = new_state()
    risk_state["_last_positions"] = [{"id": "ORD-9", "symbol": "EURUSD", "profit": -10.0}]
    telegram = _FakeTelegram()

    result = await runner._process_closed_positions([], risk_state, _FakeExecutor(), telegram)

    assert fake_journal.closes == []
    assert fake_portmgr.closed == []
    assert result["trades_today"] == 0
    assert telegram.mismatches


@pytest.mark.asyncio
async def test_losing_streak_halts_via_real_close_events(fakes):
    """Acceptance criterion from SYSTEM2_MASTER_PLAN.md Phase 1: a forced losing
    streak must actually halt new trading through the real trade-close path,
    not just through demo_risk_manager's unit tests calling record_result directly."""
    fake_journal, _ = fakes
    risk_state = new_state()
    executor = _FakeExecutor(balance=10_000.0)

    for i in range(3):
        fake_journal._open_trades = [
            {"id": i, "symbol": "EURUSD", "broker_order_id": f"ORD-{i}",
             "risk_percentage": 0.0025, "direction": "long", "entry_price": 1.1},
        ]
        risk_state["_last_positions"] = [
            # Small enough that 3x doesn't also cross the 1.5% daily-loss limit —
            # isolating the consecutive-loss halt path specifically.
            {"id": f"ORD-{i}", "symbol": "EURUSD", "profit": -20.0, "current_price": 1.09}
        ]
        risk_state = await runner._process_closed_positions([], risk_state, executor, None)

    assert risk_state["halted"] is True
    assert risk_state["halt_reason"] == "CONSECUTIVE_LOSS_LIMIT"


@pytest.mark.asyncio
async def test_missing_current_price_falls_back_to_entry_price_not_fabricated(fakes):
    fake_journal, _ = fakes
    fake_journal._open_trades = [
        {"id": 1, "symbol": "EURUSD", "broker_order_id": "ORD-1",
         "risk_percentage": 0.0025, "direction": "long", "entry_price": 1.1000},
    ]
    risk_state = new_state()
    risk_state["_last_positions"] = [{"id": "ORD-1", "symbol": "EURUSD", "profit": 10.0}]

    await runner._process_closed_positions([], risk_state, _FakeExecutor(), None)

    assert fake_journal.closes[0]["close_price"] == 1.1000


def test_state_persistence_round_trips(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "_RISK_STATE_PATH", tmp_path / "risk_state.json")
    risk_state = new_state()
    risk_state["trades_today"] = 3
    # _last_positions MUST survive a restart: it is the previous-tick snapshot
    # close-detection diffs against, so dropping it would blind detection of a
    # position that closed while the process was down (ROADMAP.md Phase 1).
    risk_state["_last_positions"] = [{"id": "ORD-1"}]
    # Other underscore-prefixed keys are transient/dashboard-only and must NOT persist.
    risk_state["_dashboard_state"] = {"status": "running"}

    runner._save_risk_state(risk_state)
    reloaded = runner._load_risk_state()

    assert reloaded["trades_today"] == 3
    assert reloaded["_last_positions"] == [{"id": "ORD-1"}]
    assert "_dashboard_state" not in reloaded


def test_load_risk_state_defaults_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "_RISK_STATE_PATH", tmp_path / "missing.json")
    assert runner._load_risk_state() == new_state()
