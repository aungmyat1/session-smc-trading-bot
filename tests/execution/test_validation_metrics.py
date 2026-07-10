"""Tests for execution/validation_metrics.py — latency percentile computation."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

_MODULE = "execution.validation_metrics"


@pytest.fixture()
def _mock_session():
    session = MagicMock()
    session_factory = MagicMock(return_value=session)
    with patch(f"{_MODULE}.SessionLocal", session_factory):
        yield session


def _row(trade_id: str, stage: str, duration_ms: float, status: str = "RECEIVED", error: str | None = None):
    return SimpleNamespace(trade_id=trade_id, stage=stage, duration_ms=duration_ms, status=status, error=error)


class TestStageLatencyStats:
    def test_computes_avg_max_and_percentiles_per_stage(self, _mock_session):
        from execution.validation_metrics import stage_latency_stats
        rows = [_row("t1", "signal_generated", d) for d in [10, 20, 30, 40, 50]]
        _mock_session.query.return_value.filter.return_value.all.return_value = rows

        result = stage_latency_stats("val-1")
        stats = result["signal_generated"]
        assert stats["count"] == 5
        assert stats["avg_ms"] == 30
        assert stats["max_ms"] == 50
        assert stats["p50_ms"] == 30

    def test_no_database_configured_returns_empty_dict(self):
        with patch(f"{_MODULE}.SessionLocal", None):
            from execution.validation_metrics import stage_latency_stats
            assert stage_latency_stats("val-1") == {}

    def test_db_failure_returns_empty_dict(self, _mock_session):
        _mock_session.query.side_effect = RuntimeError("db down")
        from execution.validation_metrics import stage_latency_stats
        assert stage_latency_stats("val-1") == {}


class TestLifecycleSuccessRate:
    def test_success_rate_excludes_rejected_and_errored_rows(self, _mock_session):
        from execution.validation_metrics import lifecycle_success_rate
        rows = [
            _row("t1", "signal_generated", 10, status="RECEIVED"),
            _row("t1", "risk_evaluation", 5, status="APPROVED"),
            _row("t2", "order_rejected", None, status="REJECTED"),
        ]
        _mock_session.query.return_value.filter.return_value.all.return_value = rows

        result = lifecycle_success_rate("val-1")
        assert result["trade_count"] == 2
        assert result["stage_count"] == 3
        assert result["failed_stage_count"] == 1
        assert result["success_rate"] == pytest.approx(2 / 3, rel=1e-3)

    def test_no_rows_returns_none_success_rate(self, _mock_session):
        from execution.validation_metrics import lifecycle_success_rate
        _mock_session.query.return_value.filter.return_value.all.return_value = []
        result = lifecycle_success_rate("val-1")
        assert result["success_rate"] is None
