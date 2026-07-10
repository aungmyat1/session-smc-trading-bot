"""Tests for execution/validation_recorder.py — per-trade lifecycle recorder."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

_MODULE = "execution.validation_recorder"


@pytest.fixture()
def _mock_session():
    session = MagicMock()
    session_factory = MagicMock(return_value=session)
    with patch(f"{_MODULE}.SessionLocal", session_factory):
        yield session


@pytest.fixture()
def recorder(_mock_session):
    from execution.validation_recorder import ValidationLifecycleRecorder
    return ValidationLifecycleRecorder("val-test-1")


class TestRecordStage:
    def test_first_stage_for_a_trade_has_no_duration(self, recorder, _mock_session):
        recorder.record_stage("trade-1", "signal_generated", "RECEIVED")
        added = _mock_session.add.call_args.args[0]
        assert added.duration_ms is None

    def test_second_stage_for_same_trade_has_a_computed_duration(self, recorder, _mock_session):
        recorder.record_stage("trade-1", "signal_generated", "RECEIVED")
        recorder.record_stage("trade-1", "risk_evaluation", "APPROVED")
        added = _mock_session.add.call_args.args[0]
        assert added.duration_ms is not None
        assert added.duration_ms >= 0

    def test_different_trade_ids_have_independent_duration_chains(self, recorder, _mock_session):
        recorder.record_stage("trade-1", "signal_generated", "RECEIVED")
        recorder.record_stage("trade-2", "signal_generated", "RECEIVED")
        added = _mock_session.add.call_args.args[0]
        assert added.duration_ms is None

    def test_db_failure_is_swallowed(self, recorder, _mock_session):
        _mock_session.commit.side_effect = RuntimeError("db down")
        recorder.record_stage("trade-1", "signal_generated", "RECEIVED")
        assert _mock_session.rollback.called

    def test_no_database_configured_does_not_raise(self):
        with patch(f"{_MODULE}.SessionLocal", None):
            from execution.validation_recorder import ValidationLifecycleRecorder
            ValidationLifecycleRecorder("val-test-1").record_stage("trade-1", "signal_generated", "RECEIVED")


class TestFromPipelineEvent:
    def _event(self, event_type: str, **overrides):
        base = {
            "event_type": event_type, "intent_id": "intent-1", "event_id": "evt-1",
            "status": "RECEIVED", "reason": "", "symbol": "EURUSD",
        }
        base.update(overrides)
        return SimpleNamespace(to_dict=lambda: base)

    def test_intent_received_maps_to_signal_generated(self, recorder, _mock_session):
        recorder.from_pipeline_event(self._event("intent_received"))
        added = _mock_session.add.call_args.args[0]
        assert added.stage == "signal_generated"
        assert added.trade_id == "intent-1"

    def test_risk_decision_maps_to_risk_evaluation(self, recorder, _mock_session):
        recorder.from_pipeline_event(self._event("risk_decision", status="APPROVED"))
        added = _mock_session.add.call_args.args[0]
        assert added.stage == "risk_evaluation"

    def test_execution_result_maps_to_order_submission(self, recorder, _mock_session):
        recorder.from_pipeline_event(self._event("execution_result", status="SUBMITTED"))
        added = _mock_session.add.call_args.args[0]
        assert added.stage == "order_submission"

    def test_rejection_events_map_to_order_rejected(self, recorder, _mock_session):
        recorder.from_pipeline_event(self._event("intent_rejected", status="REJECTED", reason="INVALID_INTENT"))
        added = _mock_session.add.call_args.args[0]
        assert added.stage == "order_rejected"
        assert added.error == "INVALID_INTENT"

    def test_unmapped_event_types_are_skipped(self, recorder, _mock_session):
        recorder.from_pipeline_event(self._event("pipeline_started"))
        assert not _mock_session.add.called
