"""Tests for svos/monitoring/service.py"""
from __future__ import annotations

from pathlib import Path


from svos.monitoring.service import MonitoringStatusService


def _make_service(tmp_path: Path, health: dict | None = None) -> MonitoringStatusService:
    def _health_factory():
        return health or {}

    return MonitoringStatusService(root=tmp_path, health_snapshot_factory=_health_factory)


def test_snapshot_healthy_no_logs(tmp_path):
    svc = _make_service(tmp_path, health={"broker": {"status": "OK"}})
    result = svc.snapshot()
    assert result["monitoring_status"] == "HEALTHY"
    assert result["incident_count"] == 0
    assert result["health"] == {"broker": {"status": "OK"}}


def test_snapshot_alert_on_fail_health(tmp_path):
    svc = _make_service(tmp_path, health={"broker": {"status": "FAIL"}})
    result = svc.snapshot()
    assert result["monitoring_status"] == "ALERT"


def test_snapshot_watch_on_log_errors(tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    (log_dir / "bot.log").write_text("INFO: started\nERROR: connection failed\n")
    svc = _make_service(tmp_path, health={})
    result = svc.snapshot()
    assert result["monitoring_status"] == "WATCH"
    assert result["incident_count"] >= 1


def test_snapshot_ignores_benign_engineio_lines(tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    (log_dir / "bot.log").write_text("engineio.client packet queue is empty, aborting\n")
    svc = _make_service(tmp_path, health={})
    result = svc.snapshot()
    assert result["monitoring_status"] == "HEALTHY"
    assert result["incident_count"] == 0


def test_snapshot_reads_multiple_log_files(tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    (log_dir / "bot.log").write_text("ERROR: broker disconnected\n")
    (log_dir / "strategy_demo.log").write_text("WARN: slow fill\n")
    svc = _make_service(tmp_path, health={})
    result = svc.snapshot()
    assert result["incident_count"] >= 2


def test_snapshot_returns_last_20_incidents(tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    lines = "\n".join(f"ERROR: event {i}" for i in range(50))
    (log_dir / "bot.log").write_text(lines + "\n")
    svc = _make_service(tmp_path, health={})
    result = svc.snapshot()
    assert len(result["recent_incidents"]) <= 20


def test_snapshot_skips_missing_log_files(tmp_path):
    # No logs directory — should not raise
    svc = _make_service(tmp_path, health={})
    result = svc.snapshot()
    assert result["monitoring_status"] == "HEALTHY"


def test_is_benign_runtime_line():
    assert MonitoringStatusService._is_benign_runtime_line(
        "engineio.client packet queue is empty, aborting"
    )
    assert not MonitoringStatusService._is_benign_runtime_line("ERROR: crash")
    assert not MonitoringStatusService._is_benign_runtime_line("")
