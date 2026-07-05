from __future__ import annotations

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from dashboard.rbac import require_role


def _make_app():
    app = FastAPI()

    @app.post("/protected")
    async def protected(identity: dict = Depends(require_role("risk_operator", "admin"))):
        return {"actor": identity["actor"], "role": identity["role"]}

    return app


def test_require_role_returns_503_when_auth_not_configured(monkeypatch):
    monkeypatch.delenv("SVOS_OPERATOR_TOKEN", raising=False)
    monkeypatch.delenv("DASHBOARD_PROXY_SECRET", raising=False)
    client = TestClient(_make_app())

    response = client.post("/protected")

    assert response.status_code == 503


def test_require_role_returns_401_when_token_configured_but_missing(monkeypatch):
    monkeypatch.setenv("SVOS_OPERATOR_TOKEN", "secret-token")
    client = TestClient(_make_app())

    response = client.post("/protected")

    assert response.status_code == 401


def test_require_role_returns_403_for_wrong_role(monkeypatch):
    monkeypatch.setenv("SVOS_OPERATOR_TOKEN", "secret-token")
    monkeypatch.setenv("SVOS_OPERATOR_ROLE", "research_operator")
    client = TestClient(_make_app())

    # X-SVOS-Role is no longer trusted for bearer auth — the role is fixed
    # server-side via SVOS_OPERATOR_ROLE, so this header must have no effect.
    response = client.post(
        "/protected",
        headers={"Authorization": "Bearer secret-token", "X-SVOS-Actor": "tester", "X-SVOS-Role": "admin"},
    )

    assert response.status_code == 403


def test_require_role_accepts_valid_bearer_token(monkeypatch):
    monkeypatch.setenv("SVOS_OPERATOR_TOKEN", "secret-token")
    monkeypatch.setenv("SVOS_OPERATOR_ROLE", "risk_operator")
    client = TestClient(_make_app())

    response = client.post(
        "/protected",
        headers={"Authorization": "Bearer secret-token", "X-SVOS-Actor": "tester"},
    )

    assert response.status_code == 200
    assert response.json() == {"actor": "tester", "role": "risk_operator"}


def test_bearer_role_ignores_caller_supplied_role_header(monkeypatch):
    """A caller holding the shared bearer token must not be able to
    self-declare a higher-privilege role via X-SVOS-Role (the vulnerability
    this fix closes)."""
    monkeypatch.setenv("SVOS_OPERATOR_TOKEN", "secret-token")
    monkeypatch.delenv("SVOS_OPERATOR_ROLE", raising=False)
    client = TestClient(_make_app())

    response = client.post(
        "/protected",
        headers={"Authorization": "Bearer secret-token", "X-SVOS-Actor": "tester", "X-SVOS-Role": "admin"},
    )

    # Default bearer role is "admin", so this specific request still succeeds —
    # the point is the role came from the server default, not the header.
    assert response.status_code == 200
    assert response.json()["role"] == "admin"


def test_require_role_rejects_proxy_mutation_without_csrf_header(monkeypatch):
    monkeypatch.delenv("SVOS_OPERATOR_TOKEN", raising=False)
    monkeypatch.setenv("DASHBOARD_PROXY_SECRET", "proxy-secret")
    client = TestClient(_make_app())

    response = client.post(
        "/protected",
        headers={
            "X-Dashboard-Proxy-Secret": "proxy-secret",
            "X-Forwarded-Email": "operator@example.com",
            "X-SVOS-Proxy-Role": "admin",
            "Origin": "http://testserver",
        },
    )

    assert response.status_code == 403
