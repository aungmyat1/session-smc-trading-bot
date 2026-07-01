from __future__ import annotations

import json
from pathlib import Path

import pytest

import dashboard.audit_log as audit_log
import dashboard.live_app as live_app
import dashboard.live_dashboard_service as live_dashboard_service


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(audit_log, "ROOT", tmp_path)
    monkeypatch.setattr(audit_log, "AUDIT_LOG_PATH", tmp_path / "logs" / "dashboard_audit.jsonl")

    monkeypatch.setattr(
        live_dashboard_service,
        "load_snapshot",
        lambda **kwargs: {
            "overview": {"account_balance": 10000, "connection_health": "CONNECTED"},
            "portfolio": {"summary": {}, "equity_curve": [], "exposure": {"long": 0, "short": 0}, "asset_allocation": []},
            "positions": {"items": [], "count": 0},
            "orders": {"pending": [], "filled": [], "cancelled": [], "rejected": [], "all": []},
            "trade_history": {"trades": []},
            "execution_monitor": {"current_execution_queue": [], "order_status": "IDLE", "fill_status": "IDLE", "retry_count": 0, "execution_latency_ms": 0},
            "risk_dashboard": {"warnings": [], "risk_limits": {}, "daily_loss_limit": 0},
            "broker_status": {"broker_connection": "CONNECTED", "mt5_status": "CONNECTED", "account_type": "demo"},
            "market_watch": {"symbols": [], "watchlist": ["EURUSD"]},
            "trading_chart": {"symbol": "EURUSD", "timeframe": "M15", "candles": []},
            "system": {"trading_mode": "demo", "demo_only": True, "vantage_demo_configured": True, "metaapi_configured": True},
            "fetched_at": "2026-06-30T00:00:00+00:00",
        },
    )
    monkeypatch.setattr(live_dashboard_service, "close_position", lambda position_id: {"ok": True, "position_id": position_id, "simulated": True})
    monkeypatch.setattr(
        live_dashboard_service,
        "modify_position",
        lambda position_id, stop_loss, take_profit: {
            "ok": True,
            "position_id": position_id,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "simulated": True,
        },
    )
    monkeypatch.setattr(live_dashboard_service, "cancel_order", lambda order_id: {"ok": True, "order_id": order_id, "simulated": True})

    live_app.app.config.update(TESTING=True, SVOS_OPERATOR_TOKEN="unit-test-operator-token")
    test_client = live_app.app.test_client()
    test_client.environ_base.update(
        {
            "HTTP_AUTHORIZATION": "Bearer unit-test-operator-token",
            "HTTP_X_SVOS_ACTOR": "unit-test-operator",
            "HTTP_X_SVOS_ROLE": "admin",
        }
    )
    return test_client


def test_live_dashboard_root_serves_standalone_dashboard(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Live Trading Dashboard" in response.data
    assert b"Operational console for Vantage demo execution" in response.data


def test_live_dashboard_api_returns_snapshot(client):
    response = client.get("/api/live-dashboard")
    payload = response.get_json()
    assert response.status_code == 200
    assert payload["overview"]["account_balance"] == 10000
    assert payload["broker_status"]["broker_connection"] == "CONNECTED"


def test_live_dashboard_health_reports_service_url(client, monkeypatch):
    monkeypatch.setenv("LIVE_DASHBOARD_PUBLIC_HOST", "live.example.com")
    monkeypatch.setenv("LIVE_DASHBOARD_PORT", "8095")
    response = client.get("/health")
    payload = response.get_json()
    assert response.status_code == 200
    assert payload["service"] == "live_dashboard"
    assert payload["url"] == "http://live.example.com:8095"


def test_live_dashboard_actions_require_auth(client):
    response = client.post(
        "/api/live-dashboard/positions/p-1/close",
        headers={"Authorization": "", "X-SVOS-Actor": "", "X-SVOS-Role": ""},
    )
    assert response.status_code == 401


def test_live_dashboard_actions_work(client):
    close_response = client.post("/api/live-dashboard/positions/p-1/close")
    assert close_response.status_code == 200
    assert close_response.get_json()["position_id"] == "p-1"

    bad_modify = client.post("/api/live-dashboard/positions/p-1/protect", json={})
    assert bad_modify.status_code == 400

    modify_response = client.post(
        "/api/live-dashboard/positions/p-1/protect",
        json={"stop_loss": 1.1, "take_profit": 1.2},
    )
    assert modify_response.status_code == 200
    assert modify_response.get_json()["take_profit"] == 1.2

    cancel_response = client.post("/api/live-dashboard/orders/o-1/cancel")
    assert cancel_response.status_code == 200
    assert cancel_response.get_json()["order_id"] == "o-1"

    audit_rows = audit_log.AUDIT_LOG_PATH.read_text(encoding="utf-8").splitlines()
    assert audit_rows
    payload = json.loads(audit_rows[-1])
    assert payload["action"] == "live_dashboard_cancel_order"
