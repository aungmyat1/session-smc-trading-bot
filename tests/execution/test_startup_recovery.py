"""
Verifies execution.startup_recovery.reconcile_pending_executions() — the fix
wiring ExecutionStateStore.recover_incomplete() to actual broker-truth
reconciliation instead of the pre-existing informational-only logging
(ROADMAP.md Phase 1 / SYSTEM2_MASTER_PLAN.md WS5).

Covers the three resolution rules plus the property this module exists to
guarantee: recovery only ever reads broker state and journal state, never
calls an order-placement API, so re-running it is always a no-op safe repeat
(no duplicate orders, no duplicate journal rows).
"""

from __future__ import annotations

from core.trade_journal_db import TradeJournalDB
from execution.execution_state import ExecutionStateStore
from execution.startup_recovery import reconcile_pending_executions


def _submission_pending(store: ExecutionStateStore, **metadata) -> str:
    record = store.create_record(
        strategy_id="ST-A2", strategy_version="1.0.0", signal_id="sig-1",
        metadata=metadata,
    )
    store.transition(record.execution_id, "RISK_APPROVED")
    store.transition(record.execution_id, "SUBMISSION_PENDING")
    return record.execution_id


def _broker_acknowledged(store: ExecutionStateStore, broker_order_id: str, **metadata) -> str:
    execution_id = _submission_pending(store, **metadata)
    store.transition(execution_id, "BROKER_ACKNOWLEDGED", broker_order_id=broker_order_id)
    return execution_id


def test_known_broker_order_id_resolves_to_completed_and_backfills_journal(tmp_path):
    store = ExecutionStateStore(tmp_path)
    journal = TradeJournalDB(tmp_path / "journal.db")
    execution_id = _broker_acknowledged(
        store, "ORD-1", symbol="EURUSD", direction="buy", lots=0.01,
    )
    positions = [{"id": "ORD-1", "symbol": "EURUSD", "direction": "buy", "lots": 0.01, "entry": 1.1000}]

    report = reconcile_pending_executions(store, journal, positions)

    assert report.recovered_count == 1
    assert report.lost_count == 0
    assert store.load(execution_id).state == "COMPLETED"
    assert journal.get_broker_order_ids() == {"ORD-1"}
    assert store.recover_incomplete() == []


def test_no_broker_order_id_but_matching_unlinked_position_is_recovered(tmp_path):
    store = ExecutionStateStore(tmp_path)
    journal = TradeJournalDB(tmp_path / "journal.db")
    execution_id = _submission_pending(store, symbol="GBPUSD", direction="sell", lots=0.02)
    positions = [{"id": "ORD-9", "symbol": "GBPUSD", "direction": "sell", "lots": 0.02, "entry": 1.25}]

    report = reconcile_pending_executions(store, journal, positions)

    assert report.recovered_count == 1
    resolved = report.resolved[0]
    assert resolved.broker_order_id == "ORD-9"
    assert store.load(execution_id).broker_order_id == "ORD-9"
    assert journal.get_broker_order_ids() == {"ORD-9"}


def test_no_broker_order_id_and_no_matching_position_is_lost_not_resubmitted(tmp_path):
    store = ExecutionStateStore(tmp_path)
    journal = TradeJournalDB(tmp_path / "journal.db")
    execution_id = _submission_pending(store, symbol="XAUUSD", direction="buy", lots=0.01)

    report = reconcile_pending_executions(store, journal, open_positions=[])

    assert report.lost_count == 1
    assert report.recovered_count == 0
    assert store.load(execution_id).state == "FAILED_TERMINAL"
    assert journal.get_all_trades() == []


def test_broker_position_with_no_execution_or_journal_link_is_orphaned(tmp_path):
    store = ExecutionStateStore(tmp_path)
    journal = TradeJournalDB(tmp_path / "journal.db")
    positions = [{"id": "ORD-ORPHAN", "symbol": "EURUSD", "direction": "buy", "lots": 0.01}]

    report = reconcile_pending_executions(store, journal, positions)

    assert report.resolved == []
    assert [p["id"] for p in report.orphaned_positions] == ["ORD-ORPHAN"]


def test_already_journaled_broker_order_id_is_not_flagged_orphaned(tmp_path):
    store = ExecutionStateStore(tmp_path)
    journal = TradeJournalDB(tmp_path / "journal.db")
    from shared.strategy_api import Signal

    journal.record_signal(
        Signal(timestamp="2026-07-04T00:00:00Z", strategy_name="ST-A2", symbol="EURUSD", action="BUY"),
        execution_result="OPEN", broker_order_id="ORD-KNOWN",
    )
    positions = [{"id": "ORD-KNOWN", "symbol": "EURUSD", "direction": "buy", "lots": 0.01}]

    report = reconcile_pending_executions(store, journal, positions)

    assert report.orphaned_positions == []


def test_rerunning_recovery_is_idempotent_no_duplicate_journal_rows_or_orders(tmp_path):
    """The core safety guarantee: recovery never calls an order-placement API,
    so running it twice against the same state must be a pure no-op the
    second time — zero new journal rows, zero state transitions attempted."""
    store = ExecutionStateStore(tmp_path)
    journal = TradeJournalDB(tmp_path / "journal.db")
    _submission_pending(store, symbol="EURUSD", direction="buy", lots=0.01)
    positions = [{"id": "ORD-5", "symbol": "EURUSD", "direction": "buy", "lots": 0.01, "entry": 1.1}]

    first = reconcile_pending_executions(store, journal, positions)
    assert first.recovered_count == 1
    rows_after_first = len(journal.get_all_trades())

    second = reconcile_pending_executions(store, journal, positions)

    assert second.resolved == []
    assert second.orphaned_positions == []
    assert len(journal.get_all_trades()) == rows_after_first
