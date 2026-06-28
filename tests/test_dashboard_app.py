"""Smoke tests for dashboard Flask app endpoints."""
from __future__ import annotations

import pytest


@pytest.fixture()
def client():
    from dashboard.app import app
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_api_status_returns_200(client):
    r = client.get("/api/status")
    assert r.status_code == 200
    data = r.get_json()
    assert data["system"] == "ONLINE"
    assert "live_trading" in data
    assert "dashboard_url" in data
    assert data["live_trading"] is False  # must never be True in tests


def test_api_svos_returns_200(client):
    r = client.get("/api/svos")
    assert r.status_code == 200
    data = r.get_json()
    assert "strategies" in data
    assert "fetched_at" in data


def test_api_evf_returns_200(client):
    r = client.get("/api/evf")
    assert r.status_code == 200
    data = r.get_json()
    assert "status" in data
    assert "fetched_at" in data


def test_api_trades_returns_200(client):
    r = client.get("/api/trades")
    assert r.status_code == 200
    data = r.get_json()
    assert "stats" in data
    assert "recent" in data


def test_api_svos_run_rejects_missing_token(client):
    r = client.post("/api/svos/run", json={"strategy": "ST-A2", "confirm_token": ""})
    assert r.status_code == 403
    data = r.get_json()
    assert "error" in data
    assert data["required"] == "CONFIRM-SVOS-ST-A2"


def test_api_evf_run_rejects_missing_token(client):
    r = client.post("/api/evf/run", json={"strategy": "ST-A2", "confirm_token": ""})
    assert r.status_code == 403
    data = r.get_json()
    assert "error" in data
    assert data["required"] == "CONFIRM-EVF-ST-A2"


def test_api_svos_run_rejects_wrong_token(client):
    r = client.post("/api/svos/run", json={"strategy": "ST-A2", "confirm_token": "WRONG"})
    assert r.status_code == 403


def test_index_serves_html(client):
    r = client.get("/")
    assert r.status_code == 200
    assert b"SMC Trading Bot" in r.data


def test_index_resets_system_status_styles_when_back_online(client):
    r = client.get("/")
    assert r.status_code == 200
    assert b"el.style.borderColor = '';" in r.data
    assert b"el.style.color = '';" in r.data
