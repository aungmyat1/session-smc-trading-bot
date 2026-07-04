"""
End-to-end acceptance test for ROADMAP.md Phase 1 / SYSTEM2_MASTER_PLAN.md
Phase 1: exercises the full chain

    Open Trade -> Broker Close -> Close Detection -> record_result()
    -> Portfolio Update -> Circuit Breaker -> SQLite Journal -> Dashboard
    -> Restart -> Recovery -> Resume Trading

against the real modules (ExecutionStateStore JSON store, SQLite
TradeJournalDB, PortfolioManager, CircuitBreaker, execution.close_reconciliation,
execution.startup_recovery, and the dashboard-facing state file) with only the
broker connector/executor and Telegram faked — no unit mocks internal calls.

Unlike tests/scripts/test_run_st_a2_demo_close_detection.py (isolated
close-handling only) and tests/execution/test_startup_recovery.py (isolated
recovery only), this test drives both across a simulated process restart to
prove the two integrate correctly and that recovery guarantees idempotency.
"""

from __future__ import annotations

import json

import pytest

import scripts.run_st_a2_demo as runner
from core.circuit_breaker import CircuitBreaker
from core.portfolio_manager import PortfolioManager
from core.trade_journal_db import TradeJournalDB
from execution.execution_state import ExecutionStateStore
from execution.startup_recovery import reconcile_pending_executions
from shared.strategy_api import Signal


class _FakeExecutor:
    def __init__(self, balance: float = 10_000.0) -> None:
        self._balance = balance

    async def get_account_info(self):
        return {"balance": self._balance}


@pytest.mark.asyncio
async def test_full_open_close_restart_recovery_resume_cycle(tmp_path, monkeypatch):
    journal_db = TradeJournalDB(tmp_path / "journal.db")
    portmgr = PortfolioManager()
    breaker = CircuitBreaker()
    execution_store = ExecutionStateStore(tmp_path)
    monkeypatch.setattr(runner, "_journal_db", journal_db)
    monkeypatch.setattr(runner, "_portmgr", portmgr)
    monkeypatch.setattr(runner, "_breaker", breaker)
    monkeypatch.setattr(runner, "_RISK_STATE_PATH", tmp_path / "risk_state.json")
    monkeypatch.setattr(runner, "_PORTFOLIO_STATE_PATH", tmp_path / "portfolio_state.json")
    monkeypatch.setattr(runner, "_STATE_PATH", tmp_path / "strategy_demo_state.json")

    # ── 1. Open Trade ────────────────────────────────────────────────────
    signal = Signal(
        timestamp="2026-07-04T08:00:00+00:00", strategy_name="ST-A2", symbol="EURUSD",
        action="BUY", entry_price=1.1000, risk_percent=0.0025,
    )
    trade_id = journal_db.record_signal(
        signal, router_result="PASS", breaker_result="PASS", portfolio_result="PASS",
        execution_result="OPEN", broker_order_id="ORD-1", position_size=0.10,
    )
    portmgr.record_trade(signal)
    execution_id = execution_store.create_record(
        strategy_id="ST-A2", strategy_version="1.0.0", signal_id="sig-1",
        metadata={"symbol": "EURUSD", "direction": "buy", "lots": 0.10},
    ).execution_id
    execution_store.transition(execution_id, "RISK_APPROVED")
    execution_store.transition(execution_id, "SUBMISSION_PENDING")
    execution_store.transition(execution_id, "BROKER_ACKNOWLEDGED", broker_order_id="ORD-1")
    execution_store.advance_to_terminal(execution_id, "COMPLETED")

    assert "EURUSD" in portmgr.export_state()["open_symbols"]
    assert journal_db.get_open_trades()[0]["id"] == trade_id

    risk_state = runner.new_state()
    risk_state["_last_positions"] = [
        {"id": "ORD-1", "symbol": "EURUSD", "profit": -30.0, "current_price": 1.0970}
    ]

    # ── 2/3. Broker Close -> Close Detection -> record_result()/Portfolio
    #        Update/Circuit Breaker/SQLite Journal ─────────────────────────
    risk_state = await runner._process_closed_positions(
        [], risk_state, _FakeExecutor(balance=10_000.0), None,
    )

    closed_trade = journal_db.get_trade(trade_id)
    assert closed_trade["status"] == "CLOSED"
    assert closed_trade["profit_loss"] == pytest.approx(-30.0)
    assert "EURUSD" not in portmgr.export_state()["open_symbols"]
    assert breaker.status()["ST-A2"]["consecutive_losses"] == 1
    assert risk_state["consecutive_losses"] == 1

    # ── 4. Dashboard ─────────────────────────────────────────────────────
    dashboard_state = {
        "open_positions": [],
        "execution_recovery_pending": len(execution_store.recover_incomplete()),
    }
    runner._write_state(dashboard_state)
    on_disk = json.loads(runner._STATE_PATH.read_text(encoding="utf-8"))
    assert on_disk["open_positions"] == []
    assert on_disk["execution_recovery_pending"] == 0  # step 1's record is already terminal

    # Persist state as the runner does before shutdown/each tick.
    runner._save_risk_state(risk_state)
    runner._save_portfolio_state()

    # Simulate a second signal whose submission was interrupted mid-flight —
    # this is the ambiguous in-flight order restart recovery must resolve.
    stuck_execution_id = execution_store.create_record(
        strategy_id="ST-A2", strategy_version="1.0.0", signal_id="sig-2",
        metadata={"symbol": "GBPUSD", "direction": "sell", "lots": 0.05},
    ).execution_id
    execution_store.transition(stuck_execution_id, "RISK_APPROVED")
    execution_store.transition(stuck_execution_id, "SUBMISSION_PENDING")
    # Crash simulated here: no BROKER_ACKNOWLEDGED ever recorded.

    # ── 5. Restart ───────────────────────────────────────────────────────
    # Fresh in-memory objects standing in for a brand-new process, reloading
    # only from the durable stores (JSON execution state, SQLite journal,
    # persisted risk/portfolio JSON) exactly as run_st_a2_demo.run() does.
    restarted_portmgr = PortfolioManager()
    restarted_portmgr.load_state(runner._load_portfolio_state())
    restarted_risk_state = runner._load_risk_state()
    restarted_store = ExecutionStateStore(tmp_path)

    assert "EURUSD" not in restarted_portmgr.export_state()["open_symbols"]
    assert restarted_risk_state["consecutive_losses"] == 1
    assert restarted_risk_state["_last_positions"] == []

    # ── 6. Recovery ──────────────────────────────────────────────────────
    # GBPUSD never reached the broker (no matching open position at restart).
    startup_positions: list[dict] = []
    recon_report = reconcile_pending_executions(restarted_store, journal_db, startup_positions)

    assert recon_report.lost_count == 1
    assert recon_report.recovered_count == 0
    assert restarted_store.load(stuck_execution_id).state == "FAILED_TERMINAL"
    # No order was ever resubmitted for the lost signal — no new journal row exists.
    assert len(journal_db.get_all_trades()) == 1

    restarted_risk_state = await runner._process_closed_positions(
        startup_positions, restarted_risk_state, _FakeExecutor(), None,
    )

    # Idempotency: re-running recovery against the same durable state changes nothing further.
    second_pass = reconcile_pending_executions(restarted_store, journal_db, startup_positions)
    assert second_pass.resolved == []
    assert len(journal_db.get_all_trades()) == 1

    # ── 7. Resume Trading ───────────────────────────────────────────────
    # PortfolioManager's one-per-symbol guard is clear for both symbols —
    # a fresh EURUSD or GBPUSD signal would not be blocked by a stale open lock.
    assert restarted_portmgr.export_state()["open_symbols"] == []
    assert restarted_risk_state["halted"] is False
    runner._write_state({
        "open_positions": [],
        "execution_recovery_pending": len(restarted_store.recover_incomplete()),
    })
    resumed_dashboard_state = json.loads(runner._STATE_PATH.read_text(encoding="utf-8"))
    assert resumed_dashboard_state["execution_recovery_pending"] == 0
