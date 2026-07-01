from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

import dashboard.control_state as control_state
import dashboard.status_server as status_server


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_metrics_endpoint_and_emergency_routes(tmp_path, monkeypatch):
    monkeypatch.setattr(status_server, "ROOT", tmp_path)
    monkeypatch.setattr(control_state, "CONTROL_STATE_PATH", tmp_path / "reports" / "control_state.json")
    _write(
        tmp_path / "logs" / "strategy_demo_state.json",
        json.dumps(
            {
                "status": "running",
                "last_tick_at": "2026-07-01T10:00:00+00:00",
                "open_positions": [{"id": "POS-1"}],
                "account": {"balance": 1000, "equity": 1002, "free_margin": 800},
            }
        ),
    )
    client = TestClient(status_server.app)

    denied = client.post("/api/emergency-stop", json={"reason": "manual pause"})
    assert denied.status_code == 403
    assert denied.json()["required"] == "CONFIRM-EMERGENCY-STOP"

    accepted = client.post(
        "/api/emergency-stop",
        json={"reason": "manual pause", "confirm_token": "CONFIRM-EMERGENCY-STOP"},
    )
    assert accepted.status_code == 200
    assert accepted.json()["emergency_stop"]["active"] is True

    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    assert "smc_runner_connected 1" in metrics.text
    assert "smc_emergency_stop_active 1" in metrics.text
    assert "smc_trading_allowed" in metrics.text

    control_snapshot = client.get("/api/control/permission")
    assert control_snapshot.status_code == 200
    assert "mode" in control_snapshot.json()

    health = client.get("/api/health/summary")
    assert health.status_code == 200
    assert "score" in health.json()

    readiness = client.get("/api/readiness/report")
    assert readiness.status_code == 200
    assert "html_report" in readiness.json()

    cleared = client.post(
        "/api/emergency-stop/clear",
        json={"reason": "resume", "confirm_token": "CONFIRM-CLEAR-EMERGENCY-STOP"},
    )
    assert cleared.status_code == 200
    assert cleared.json()["emergency_stop"]["active"] is False
