"""
Verifies execution/operations_recorder.py — the Sprint 2.3 (SYSTEM2_MASTER_PLAN.md
Phase 2) durable audit trail into the Postgres operations.* schema (migration 004).
Mocks db.connection.SessionLocal so no live database is required, matching this
repo's existing DB-test convention (tests/database/test_db_preflight.py).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from db.models import ExecutionEvent, Fill, Intent, OrderRecord, PositionRecord, Reconciliation, RecoveryCheckpoint, RiskDecision, Runtime
from execution.operations_recorder import OperationsRecorder, db_health_check, record_fill, record_position, record_reconciliation


class _FakeEvent:
    def __init__(self, event_type: str, **fields) -> None:
        self._data = {"event_type": event_type, "event_id": "evt-1", "intent_id": "ST-A2:EURUSD:t1", **fields}

    def to_dict(self) -> dict:
        return dict(self._data)


def _fake_session():
    session = MagicMock()
    session.add = MagicMock()
    return session


def test_record_runtime_start_adds_one_row():
    session = _fake_session()
    with patch("execution.operations_recorder.SessionLocal", return_value=session):
        OperationsRecorder("rt-1").record_runtime_start(status="running", strategy="ST-A2")
    added = session.add.call_args[0][0]
    assert isinstance(added, Runtime)
    assert added.runtime_id == "rt-1"
    session.commit.assert_called_once()


def test_event_sink_always_logs_execution_event():
    session = _fake_session()
    with patch("execution.operations_recorder.SessionLocal", return_value=session):
        OperationsRecorder("rt-1").event_sink(_FakeEvent("pipeline_started"))
    assert isinstance(session.add.call_args[0][0], ExecutionEvent)


def test_intent_received_also_writes_intent_row():
    session = _fake_session()
    with patch("execution.operations_recorder.SessionLocal", return_value=session):
        OperationsRecorder("rt-1").event_sink(_FakeEvent("intent_received", symbol="EURUSD"))
    kinds = [type(c.args[0]) for c in session.add.call_args_list]
    assert ExecutionEvent in kinds and Intent in kinds


def test_risk_decision_also_writes_risk_decision_row():
    session = _fake_session()
    with patch("execution.operations_recorder.SessionLocal", return_value=session):
        OperationsRecorder("rt-1").event_sink(_FakeEvent("risk_decision", approved=True))
    kinds = [type(c.args[0]) for c in session.add.call_args_list]
    assert RiskDecision in kinds
    risk_row = next(c.args[0] for c in session.add.call_args_list if isinstance(c.args[0], RiskDecision))
    assert risk_row.approved is True


def test_execution_result_also_writes_order_record_row():
    session = _fake_session()
    with patch("execution.operations_recorder.SessionLocal", return_value=session):
        OperationsRecorder("rt-1").event_sink(_FakeEvent("execution_result", status="SUBMITTED", reference="ORD-1"))
    order_row = next(c.args[0] for c in session.add.call_args_list if isinstance(c.args[0], OrderRecord))
    assert order_row.order_id == "ORD-1"
    assert order_row.idempotency_key == "ST-A2:EURUSD:t1"


def test_recovery_checkpoint_records_resolved_and_orphaned():
    session = _fake_session()
    resolved = [MagicMock(execution_id="e1", final_state="COMPLETED", broker_order_id="ORD-1", note="recovered")]
    with patch("execution.operations_recorder.SessionLocal", return_value=session):
        OperationsRecorder("rt-1").record_recovery_checkpoint(resolved, [{"id": "ORD-ORPHAN"}])
    row = session.add.call_args[0][0]
    assert isinstance(row, RecoveryCheckpoint)
    assert row.state["resolved"][0]["execution_id"] == "e1"
    assert row.state["orphaned_positions"] == [{"id": "ORD-ORPHAN"}]


def test_db_write_failure_is_swallowed_not_raised():
    session = _fake_session()
    session.commit.side_effect = RuntimeError("db down")
    with patch("execution.operations_recorder.SessionLocal", return_value=session):
        OperationsRecorder("rt-1").record_runtime_start()  # must not raise
    session.rollback.assert_called_once()


def test_no_database_configured_is_a_silent_noop():
    with patch("execution.operations_recorder.SessionLocal", None):
        OperationsRecorder("rt-1").record_runtime_start()  # must not raise


# ── db_health_check() — System 2 readiness aggregator's DB probe ─────────────

def test_db_health_check_not_configured_reports_unreachable_not_skipped():
    """No DATABASE_URL must be reported as an explicit failure, not silently
    treated as 'not applicable' — the readiness aggregator fails closed on
    this exact distinction (configured=False vs configured=True, unreachable)."""
    with patch("execution.operations_recorder.SessionLocal", None):
        result = db_health_check()
    assert result == {"reachable": False, "configured": False, "latency_ms": None, "error": "DATABASE_URL not configured"}


def test_db_health_check_reachable_reports_latency():
    session = _fake_session()
    with patch("execution.operations_recorder.SessionLocal", return_value=session):
        result = db_health_check()
    assert result["reachable"] is True
    assert result["configured"] is True
    assert result["error"] is None
    assert isinstance(result["latency_ms"], float)
    session.execute.assert_called_once()
    session.close.assert_called_once()


def test_db_health_check_query_failure_reports_unreachable_but_configured():
    session = _fake_session()
    session.execute.side_effect = RuntimeError("connection refused")
    with patch("execution.operations_recorder.SessionLocal", return_value=session):
        result = db_health_check()
    assert result["reachable"] is False
    assert result["configured"] is True
    assert "connection refused" in result["error"]
    session.close.assert_called_once()  # session is always closed, even on failure


# ── Dormant-table writers (2026-07-06, Demo Validation Mode) ────────────────
# operations.fill / position_record / reconciliation were defined by
# migration 004 but had zero writers anywhere in the codebase until Demo
# Validation Mode's ValidationLifecycleRecorder became their first caller.


def test_record_fill_adds_one_row():
    session = _fake_session()
    with patch("execution.operations_recorder.SessionLocal", return_value=session):
        record_fill("order-1", "FILLED", {"symbol": "EURUSD"})
    added = session.add.call_args[0][0]
    assert isinstance(added, Fill)
    assert added.order_id == "order-1"
    assert added.status == "FILLED"
    session.commit.assert_called_once()


def test_record_fill_db_failure_is_swallowed():
    session = _fake_session()
    session.commit.side_effect = RuntimeError("db down")
    with patch("execution.operations_recorder.SessionLocal", return_value=session):
        record_fill("order-1", "FILLED", {})  # must not raise
    session.rollback.assert_called_once()


def test_record_position_adds_one_row():
    session = _fake_session()
    with patch("execution.operations_recorder.SessionLocal", return_value=session):
        record_position("EURUSD", "OPEN", {"lots": 0.1})
    added = session.add.call_args[0][0]
    assert isinstance(added, PositionRecord)
    assert added.symbol == "EURUSD"
    session.commit.assert_called_once()


def test_record_reconciliation_adds_one_row():
    session = _fake_session()
    with patch("execution.operations_recorder.SessionLocal", return_value=session):
        record_reconciliation("rt-1", True, {"orphans": 0})
    added = session.add.call_args[0][0]
    assert isinstance(added, Reconciliation)
    assert added.consistent is True
    session.commit.assert_called_once()


def test_writers_are_no_ops_when_database_unconfigured():
    with patch("execution.operations_recorder.SessionLocal", None):
        record_fill("order-1", "FILLED", {})
        record_position("EURUSD", "OPEN", {})
        record_reconciliation("rt-1", True, {})  # none of these should raise
