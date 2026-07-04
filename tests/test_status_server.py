from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

import dashboard.control_state as control_state
import dashboard.status_server as status_server


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


_OPERATOR_HEADERS = {
    "Authorization": "Bearer test-operator-token",
    "X-SVOS-Actor": "tester",
    "X-SVOS-Role": "risk_operator",
}


def test_metrics_endpoint_and_emergency_routes(tmp_path, monkeypatch):
    monkeypatch.setattr(status_server, "ROOT", tmp_path)
    monkeypatch.setattr(control_state, "CONTROL_STATE_PATH", tmp_path / "reports" / "control_state.json")
    monkeypatch.setenv("SVOS_OPERATOR_TOKEN", "test-operator-token")
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

    unauthenticated = client.post("/api/emergency-stop", json={"reason": "manual pause"})
    assert unauthenticated.status_code == 401

    denied = client.post(
        "/api/emergency-stop", json={"reason": "manual pause"}, headers=_OPERATOR_HEADERS
    )
    assert denied.status_code == 403
    assert denied.json()["required"] == "CONFIRM-EMERGENCY-STOP"

    accepted = client.post(
        "/api/emergency-stop",
        json={"reason": "manual pause", "confirm_token": "CONFIRM-EMERGENCY-STOP"},
        headers=_OPERATOR_HEADERS,
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
        headers=_OPERATOR_HEADERS,
    )
    assert cleared.status_code == 200
    assert cleared.json()["emergency_stop"]["active"] is False


def test_operator_control_endpoints_require_role_and_confirm_token(tmp_path, monkeypatch):
    monkeypatch.setattr(status_server, "ROOT", tmp_path)
    monkeypatch.setattr(control_state, "CONTROL_STATE_PATH", tmp_path / "reports" / "control_state.json")
    monkeypatch.setenv("SVOS_OPERATOR_TOKEN", "test-operator-token")
    _write(
        tmp_path / "logs" / "strategy_demo_state.json",
        json.dumps({"status": "running", "strategy": "ST-A2"}),
    )
    client = TestClient(status_server.app)

    forbidden_role_headers = {**_OPERATOR_HEADERS, "X-SVOS-Role": "research_operator"}
    forbidden = client.post(
        "/api/control/pause",
        json={"confirm_token": "CONFIRM-PAUSE-TRADING"},
        headers=forbidden_role_headers,
    )
    assert forbidden.status_code == 403

    paused = client.post(
        "/api/control/pause", json={"confirm_token": "CONFIRM-PAUSE-TRADING"}, headers=_OPERATOR_HEADERS
    )
    assert paused.status_code == 200
    assert paused.json()["status"] == "paused"
    assert paused.json()["emergency_stop"]["scope"] == "block_only"

    resumed = client.post(
        "/api/control/resume", json={"confirm_token": "CONFIRM-RESUME-TRADING"}, headers=_OPERATOR_HEADERS
    )
    assert resumed.status_code == 200
    assert resumed.json()["status"] == "resumed"

    close_all = client.post(
        "/api/control/close-all",
        json={"confirm_token": "CONFIRM-CLOSE-ALL-POSITIONS"},
        headers=_OPERATOR_HEADERS,
    )
    assert close_all.status_code == 200
    assert close_all.json()["emergency_stop"]["scope"] == "close_positions"
    client.post(
        "/api/control/resume", json={"confirm_token": "CONFIRM-RESUME-TRADING"}, headers=_OPERATOR_HEADERS
    )

    mismatch = client.post(
        "/api/control/toggle-strategy",
        json={"strategy_id": "OtherStrategy", "action": "pause", "confirm_token": "CONFIRM-TOGGLE-STRATEGY-OtherStrategy"},
        headers=_OPERATOR_HEADERS,
    )
    assert mismatch.status_code == 409
    assert mismatch.json()["status"] == "no_op"

    bad_token = client.post(
        "/api/control/toggle-strategy",
        json={"strategy_id": "ST-A2", "action": "pause", "confirm_token": "wrong-token"},
        headers=_OPERATOR_HEADERS,
    )
    assert bad_token.status_code == 403

    toggled = client.post(
        "/api/control/toggle-strategy",
        json={"strategy_id": "ST-A2", "action": "pause", "confirm_token": "CONFIRM-TOGGLE-STRATEGY-ST-A2"},
        headers=_OPERATOR_HEADERS,
    )
    assert toggled.status_code == 200
    assert toggled.json()["status"] == "strategy_paused"
    assert toggled.json()["emergency_stop"]["active"] is True


def test_new_dashboard_live_state_delegates_to_live_state_adapter(tmp_path, monkeypatch):
    """Phase 6 dashboard integration: the deployed backend's copy of
    /api/new-dashboard/live-state must be a pure passthrough to
    live_state_adapter.build_live_state(), not a reimplementation."""
    monkeypatch.setattr(status_server, "ROOT", tmp_path)
    fake_state = {"pairs": {}, "selectedPair": "EURUSD", "health": {}, "unavailable": []}
    with patch.object(status_server.live_state_adapter, "build_live_state", return_value=fake_state) as mock_build:
        client = TestClient(status_server.app)
        response = client.get("/api/new-dashboard/live-state?symbol=EURUSD&timeframe=M15&candle_count=50")
    assert response.status_code == 200
    assert response.json() == fake_state
    mock_build.assert_called_once_with(chart_symbol="EURUSD", timeframe="M15", candle_count=50)


def _base_operations_state(tmp_path: Path) -> None:
    _write(
        tmp_path / "logs" / "strategy_demo_state.json",
        json.dumps(
            {
                "status": "running", "strategy": "ST-A2", "mode": "demo",
                "started_at": "2026-07-04T17:00:00+00:00",
                "last_tick_at": "2026-07-04T17:05:00+00:00",
                "broker_status": "connected", "open_positions": [], "pairs": ["EURUSD"],
            }
        ),
    )


def test_operations_health_reports_uptime_and_deployment_info(tmp_path, monkeypatch):
    monkeypatch.setattr(status_server, "ROOT", tmp_path)
    monkeypatch.setattr(control_state, "CONTROL_STATE_PATH", tmp_path / "reports" / "control_state.json")
    _base_operations_state(tmp_path)
    client = TestClient(status_server.app)

    response = client.get("/api/operations/health")

    assert response.status_code == 200
    body = response.json()
    assert body["source"]
    assert body["data"]["execution_runner"]["strategy"] == "ST-A2"
    assert body["data"]["execution_runner"]["uptime_seconds"] is not None
    assert "redis" in " ".join(body["unavailable"])


def test_operations_risk_reads_persisted_state_not_live_recalculation(tmp_path, monkeypatch):
    monkeypatch.setattr(status_server, "ROOT", tmp_path)
    monkeypatch.setattr(control_state, "CONTROL_STATE_PATH", tmp_path / "reports" / "control_state.json")
    _base_operations_state(tmp_path)
    _write(
        tmp_path / "logs" / "risk_state.json",
        json.dumps({"consecutive_losses": 2, "halted": True, "halt_reason": "CONSECUTIVE_LOSS_LIMIT"}),
    )
    _write(tmp_path / "logs" / "portfolio_state.json", json.dumps({"weekly_pnl_pct": -0.01, "open_symbols": ["EURUSD"]}))
    with patch.object(status_server.live_dashboard_service, "load_snapshot", return_value={"risk_dashboard": {}}):
        client = TestClient(status_server.app)
        response = client.get("/api/operations/risk")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["consecutive_losses"] == 2
    assert data["halted"] is True
    assert data["halt_reason"] == "CONSECUTIVE_LOSS_LIMIT"
    assert data["open_symbols"] == ["EURUSD"]


def test_operations_events_reads_from_operations_recorder(tmp_path, monkeypatch):
    monkeypatch.setattr(status_server, "ROOT", tmp_path)
    with (
        patch.object(status_server, "get_recent_events", return_value=[{"type": "execution_event", "event_type": "pipeline_started"}]) as mock_events,
        patch.object(status_server, "get_recent_runtimes", return_value=[{"runtime_id": "abc", "status": "running"}]) as mock_runtimes,
    ):
        client = TestClient(status_server.app)
        response = client.get("/api/operations/events?limit=10")

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["events"][0]["event_type"] == "pipeline_started"
    assert body["data"]["startup_events"][0]["runtime_id"] == "abc"
    assert "telegram_alert_history" in " ".join(body["unavailable"])
    mock_events.assert_called_once_with(limit=10)
    mock_runtimes.assert_called_once_with(limit=10)


def test_all_operations_endpoints_return_200_with_consistent_envelope(tmp_path, monkeypatch):
    """Smoke test across the full Phase 5 endpoint family."""
    monkeypatch.setattr(status_server, "ROOT", tmp_path)
    monkeypatch.setattr(control_state, "CONTROL_STATE_PATH", tmp_path / "reports" / "control_state.json")
    _base_operations_state(tmp_path)
    fake_snapshot = {
        "portfolio": {"summary": {}, "daily_statistics": {}}, "positions": {"items": [], "count": 0},
        "orders": {}, "execution_monitor": {}, "trade_history": {"trades": []}, "risk_dashboard": {},
    }
    with (
        patch.object(status_server.live_dashboard_service, "load_snapshot", return_value=fake_snapshot),
        patch.object(status_server, "get_recent_events", return_value=[]),
        patch.object(status_server, "get_recent_runtimes", return_value=[]),
    ):
        client = TestClient(status_server.app)
        for endpoint in ("health", "account", "positions", "orders", "trades", "strategy", "risk", "events"):
            response = client.get(f"/api/operations/{endpoint}")
            assert response.status_code == 200, endpoint
            body = response.json()
            assert set(body.keys()) == {"data", "source", "fetched_at", "unavailable"}, endpoint


def test_realtime_operations_layer_endpoints_return_200_with_real_sources(tmp_path, monkeypatch):
    """Real-Time Operations Layer Phase 2: /overview, /live/trades, /svos/status,
    /strategies/performance, /system/health must all be reachable and each
    delegate to an existing service rather than recomputing data."""
    monkeypatch.setattr(status_server, "ROOT", tmp_path)
    monkeypatch.setattr(control_state, "CONTROL_STATE_PATH", tmp_path / "reports" / "control_state.json")
    _base_operations_state(tmp_path)
    fake_snapshot = {
        "portfolio": {"summary": {}, "daily_statistics": {}}, "positions": {"items": [], "count": 0},
        "orders": {}, "execution_monitor": {}, "trade_history": {"trades": []}, "risk_dashboard": {},
    }
    with (
        patch.object(status_server.live_dashboard_service, "load_snapshot", return_value=fake_snapshot),
        patch.object(status_server, "get_recent_events", return_value=[]),
        patch.object(status_server, "get_recent_runtimes", return_value=[]),
    ):
        client = TestClient(status_server.app)
        for path in ("/overview", "/live/trades", "/svos/status", "/strategies/performance", "/system/health"):
            response = client.get(path)
            assert response.status_code == 200, path


def test_websocket_ws_endpoint_delivers_published_events(tmp_path, monkeypatch):
    monkeypatch.setattr(status_server, "ROOT", tmp_path)
    client = TestClient(status_server.app)
    from dashboard.events import make_system_event

    with client.websocket_connect("/ws") as websocket:
        status_server._event_broadcaster.publish(make_system_event("test_event", note="hello"))
        message = websocket.receive_json()

    assert message["event_type"] == "test_event"
    assert message["source_system"] == "system"
    assert message["payload"]["note"] == "hello"


def test_load_log_prefers_most_recently_written_file_not_first_existing(tmp_path, monkeypatch):
    """Bug fixed 2026-07-04: the deployed /dashboard/ route was showing a stale,
    3-day-old log (smc_ob_fvg_demo.log) instead of the actually-live
    strategy_demo.log, because the old code returned the first candidate that
    merely *existed* rather than the one actually being written to."""
    monkeypatch.setattr(status_server, "ROOT", tmp_path)
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    stale = logs_dir / "smc_ob_fvg_demo.log"
    fresh = logs_dir / "strategy_demo.log"
    stale.write_text("OLD STALE LINE\n")
    fresh.write_text("CURRENT LIVE LINE\n")
    import os
    import time
    old_time = time.time() - 3 * 24 * 3600
    os.utime(stale, (old_time, old_time))

    result = status_server._load_log(n=5)

    assert result == ["CURRENT LIVE LINE"]
