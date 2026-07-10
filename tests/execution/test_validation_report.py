"""Tests for execution/validation_report.py — report file generation."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest


@pytest.fixture()
def _mocked_dependencies(monkeypatch):
    import execution.validation_report as report_module

    session_manager = MagicMock()
    session_manager.resume.return_value = {
        "session_id": "val-1", "operator": "alice", "broker": "vantage-mt5-demo",
        "account": "12345", "software_version": "0.1.0", "git_commit": "abc123",
        "config_hash": "def456", "status": "completed", "started_at": "2026-07-06T00:00:00+00:00",
        "ended_at": "2026-07-06T01:00:00+00:00",
    }

    monkeypatch.setattr(report_module, "stage_latency_stats", lambda session_id: {
        "signal_generated": {"count": 5, "avg_ms": 12.0, "max_ms": 30.0, "p50_ms": 10.0, "p95_ms": 25.0, "p99_ms": 29.0},
    })
    monkeypatch.setattr(report_module, "lifecycle_success_rate", lambda session_id: {
        "trade_count": 5, "stage_count": 15, "failed_stage_count": 0, "success_rate": 1.0,
    })
    monkeypatch.setattr(report_module, "get_recent_events", lambda limit=50: [])
    monkeypatch.setattr(report_module, "get_recent_runtimes", lambda limit=10: [])
    monkeypatch.setattr(report_module, "db_health_check", lambda: {"reachable": True, "latency_ms": 1.2})

    risk_store = MagicMock()
    risk_store.load_risk_state.return_value = {"halted": False}
    risk_store.load_portfolio_state.return_value = {"open_symbols": []}
    monkeypatch.setattr(report_module, "RiskPortfolioStore", lambda: risk_store)

    return session_manager


class TestGenerateReport:
    def test_writes_all_expected_json_files_and_markdown(self, tmp_path, _mocked_dependencies):
        from execution.validation_report import generate_report

        files = generate_report("val-1", output_dir=tmp_path, session_manager=_mocked_dependencies)

        expected_keys = {
            "session_summary", "trade_lifecycle", "latency_summary", "broker_health",
            "dashboard_health", "telegram_health", "ledger_health", "recovery_summary",
            "validation_report",
        }
        assert set(files.keys()) == expected_keys
        for path in files.values():
            assert path.exists()

    def test_session_summary_contains_the_resolved_session(self, tmp_path, _mocked_dependencies):
        from execution.validation_report import generate_report

        files = generate_report("val-1", output_dir=tmp_path, session_manager=_mocked_dependencies)
        data = json.loads(files["session_summary"].read_text(encoding="utf-8"))
        assert data["session"]["session_id"] == "val-1"
        assert data["lifecycle"]["trade_count"] == 5

    def test_markdown_report_includes_promotion_readiness_section(self, tmp_path, _mocked_dependencies):
        from execution.validation_report import generate_report

        files = generate_report("val-1", output_dir=tmp_path, session_manager=_mocked_dependencies)
        markdown = files["validation_report"].read_text(encoding="utf-8")
        assert "## Promotion readiness" in markdown
        assert "PENDING" in markdown  # trade_count=5 < minimum 20
