"""
Verifies execution/operations_recorder.py — the Sprint 2.3 (SYSTEM2_MASTER_PLAN.md
Phase 2) durable audit trail into the Postgres operations.* schema (migration 004).
Mocks db.connection.SessionLocal so no live database is required, matching this
repo's existing DB-test convention (tests/database/test_db_preflight.py).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from db.models import ExecutionEvent, Intent, OrderRecord, RecoveryCheckpoint, RiskDecision, Runtime
from execution.operations_recorder import OperationsRecorder


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
