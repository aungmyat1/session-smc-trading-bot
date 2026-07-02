from __future__ import annotations

import dashboard.app as dashboard_app


def _clear_auth_env(monkeypatch) -> None:
    for key in (
        "SVOS_OPERATOR_TOKEN",
        "DASHBOARD_PROXY_SECRET",
        "DASHBOARD_PROXY_SECRET_HEADER",
        "DASHBOARD_PROXY_ACTOR_HEADER",
        "DASHBOARD_PROXY_ROLE_HEADER",
        "DASHBOARD_CSRF_COOKIE_NAME",
        "DASHBOARD_CSRF_HEADER_NAME",
    ):
        monkeypatch.delenv(key, raising=False)


def test_session_me_returns_unauthenticated_payload_when_no_identity(monkeypatch):
    _clear_auth_env(monkeypatch)
    client = dashboard_app.app.test_client()

    response = client.get("/api/session/me")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["authenticated"] is False
    assert payload["mutation_allowed"] is False
    assert payload["actor"] == ""
    assert payload["role"] == ""


def test_session_me_supports_bearer_identity(monkeypatch):
    _clear_auth_env(monkeypatch)
    monkeypatch.setenv("SVOS_OPERATOR_TOKEN", "token-123")
    client = dashboard_app.app.test_client()

    response = client.get(
        "/api/session/me",
        headers={
            "Authorization": "Bearer token-123",
            "X-SVOS-Actor": "ops@example.com",
            "X-SVOS-Role": "risk_operator",
        },
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["authenticated"] is True
    assert payload["actor"] == "ops@example.com"
    assert payload["role"] == "risk_operator"
    assert payload["auth_mode"] == "bearer"
    assert "positions:close" in payload["permitted_actions"]


def test_session_me_sets_csrf_cookie_for_proxy_identity(monkeypatch):
    _clear_auth_env(monkeypatch)
    monkeypatch.setenv("DASHBOARD_PROXY_SECRET", "proxy-secret")
    client = dashboard_app.app.test_client()

    response = client.get(
        "/api/session/me",
        headers={
            "X-Dashboard-Proxy-Secret": "proxy-secret",
            "X-Forwarded-Email": "research@example.com",
            "X-SVOS-Proxy-Role": "research_operator",
        },
        base_url="http://localhost",
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["authenticated"] is True
    assert payload["auth_mode"] == "proxy"
    assert "dashboard_csrf=" in response.headers.get("Set-Cookie", "")


def test_proxy_mutation_requires_csrf_token(monkeypatch):
    _clear_auth_env(monkeypatch)
    monkeypatch.setenv("DASHBOARD_PROXY_SECRET", "proxy-secret")
    monkeypatch.setattr(
        dashboard_app,
        "generate_reports_payload",
        lambda report_type: {"type": report_type, "artifacts": []},
    )
    client = dashboard_app.app.test_client()

    response = client.post(
        "/api/reports/generate",
        json={"type": "daily"},
        headers={
            "Origin": "http://localhost",
            "X-Dashboard-Proxy-Secret": "proxy-secret",
            "X-Forwarded-Email": "research@example.com",
            "X-SVOS-Proxy-Role": "research_operator",
        },
        base_url="http://localhost",
    )
    payload = response.get_json()

    assert response.status_code == 403
    assert payload["code"] == "csrf_failed"


def test_proxy_mutation_accepts_valid_csrf_token(monkeypatch):
    _clear_auth_env(monkeypatch)
    monkeypatch.setenv("DASHBOARD_PROXY_SECRET", "proxy-secret")
    monkeypatch.setattr(
        dashboard_app,
        "generate_reports_payload",
        lambda report_type: {"type": report_type, "artifacts": [{"path": "reports/daily.md"}]},
    )
    client = dashboard_app.app.test_client()

    session_response = client.get(
        "/api/session/me",
        headers={
            "X-Dashboard-Proxy-Secret": "proxy-secret",
            "X-Forwarded-Email": "research@example.com",
            "X-SVOS-Proxy-Role": "research_operator",
        },
        base_url="http://localhost",
    )
    cookie = session_response.headers.get("Set-Cookie", "")
    token = cookie.split("dashboard_csrf=", 1)[1].split(";", 1)[0]

    response = client.post(
        "/api/reports/generate",
        json={"type": "daily"},
        headers={
            "Origin": "http://localhost",
            "X-CSRF-Token": token,
            "X-Dashboard-Proxy-Secret": "proxy-secret",
            "X-Forwarded-Email": "research@example.com",
            "X-SVOS-Proxy-Role": "research_operator",
        },
        base_url="http://localhost",
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["type"] == "daily"


def test_spoofed_proxy_headers_are_rejected(monkeypatch):
    _clear_auth_env(monkeypatch)
    monkeypatch.setenv("DASHBOARD_PROXY_SECRET", "proxy-secret")
    client = dashboard_app.app.test_client()

    response = client.post(
        "/api/reports/generate",
        json={"type": "daily"},
        headers={
            "Origin": "http://localhost",
            "X-Forwarded-Email": "research@example.com",
            "X-SVOS-Proxy-Role": "research_operator",
        },
        base_url="http://localhost",
    )
    payload = response.get_json()

    assert response.status_code == 401
    assert payload["code"] == "unauthorized"
