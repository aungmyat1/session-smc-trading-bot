"""Tests for dashboard/status_server.py's /api/validation/* read endpoints."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

import dashboard.status_server as status_server

_OPERATOR_HEADERS = {
    "Authorization": "Bearer test-operator-token",
    "X-SVOS-Actor": "tester",
}


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("SVOS_OPERATOR_TOKEN", "test-operator-token")
    return TestClient(status_server.app)


def test_validation_session_requires_auth(client):
    response = client.get("/api/validation/session")
    assert response.status_code == 401


def test_validation_session_returns_active_session(client, monkeypatch):
    stub = MagicMock()
    stub.active_session.return_value = {"session_id": "val-abc", "status": "active"}
    monkeypatch.setattr(status_server, "_validation_session_mgr", stub)

    response = client.get("/api/validation/session", headers=_OPERATOR_HEADERS)
    assert response.status_code == 200
    assert response.json()["session"]["session_id"] == "val-abc"


def test_validation_session_resumes_by_id(client, monkeypatch):
    stub = MagicMock()
    stub.resume.return_value = {"session_id": "val-xyz", "status": "completed"}
    monkeypatch.setattr(status_server, "_validation_session_mgr", stub)

    response = client.get("/api/validation/session?session_id=val-xyz", headers=_OPERATOR_HEADERS)
    assert response.status_code == 200
    stub.resume.assert_called_once_with("val-xyz")


def test_validation_lifecycle_requires_session_id(client):
    response = client.get("/api/validation/lifecycle", headers=_OPERATOR_HEADERS)
    assert response.status_code == 422


def test_validation_lifecycle_returns_stats(client, monkeypatch):
    monkeypatch.setattr(
        status_server, "lifecycle_success_rate",
        lambda session_id: {"trade_count": 3, "stage_count": 9, "failed_stage_count": 0, "success_rate": 1.0},
    )
    response = client.get("/api/validation/lifecycle?session_id=val-abc", headers=_OPERATOR_HEADERS)
    assert response.status_code == 200
    assert response.json()["lifecycle"]["trade_count"] == 3


def test_validation_latency_returns_stage_stats(client, monkeypatch):
    monkeypatch.setattr(
        status_server, "stage_latency_stats",
        lambda session_id, stage=None: {"signal_generated": {"count": 1, "avg_ms": 5.0}},
    )
    response = client.get("/api/validation/latency?session_id=val-abc", headers=_OPERATOR_HEADERS)
    assert response.status_code == 200
    assert "signal_generated" in response.json()["latency"]


def test_validation_recovery_filters_to_recovery_checkpoints(client, monkeypatch):
    monkeypatch.setattr(
        status_server, "get_recent_events",
        lambda limit=50: [
            {"type": "recovery_checkpoint", "runtime_id": "r1"},
            {"type": "execution_event", "event_type": "intent_received"},
        ],
    )
    response = client.get("/api/validation/recovery", headers=_OPERATOR_HEADERS)
    assert response.status_code == 200
    events = response.json()["recovery_events"]
    assert len(events) == 1
    assert events[0]["runtime_id"] == "r1"
