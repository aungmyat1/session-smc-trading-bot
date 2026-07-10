from __future__ import annotations

import time

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from dashboard.rbac import mint_ws_ticket, require_role, validate_ws_ticket


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


# ── WebSocket ticket auth (2026-07-05) ────────────────────────────────────────
# Browsers cannot set Authorization/X-SVOS-Actor headers on a WebSocket
# upgrade request, so /ws (dashboard/status_server.py) needs a browser-
# compatible auth path. mint_ws_ticket()/validate_ws_ticket() carry an
# already-established identity onto the WS handshake via a query param —
# see dashboard/rbac.py's module docstring for the full rationale.

def test_mint_and_validate_ws_ticket_round_trips(monkeypatch):
    monkeypatch.setenv("SVOS_OPERATOR_TOKEN", "secret-token")
    ticket = mint_ws_ticket({"actor": "tester", "role": "admin"})

    identity = validate_ws_ticket(ticket)

    assert identity == {"actor": "tester", "role": "admin", "auth_mode": "ws-ticket"}


def test_ws_ticket_is_single_use(monkeypatch):
    monkeypatch.setenv("SVOS_OPERATOR_TOKEN", "secret-token")
    ticket = mint_ws_ticket({"actor": "tester", "role": "admin"})

    assert validate_ws_ticket(ticket) is not None
    assert validate_ws_ticket(ticket) is None  # replay rejected


def test_ws_ticket_rejects_tampered_signature(monkeypatch):
    monkeypatch.setenv("SVOS_OPERATOR_TOKEN", "secret-token")
    ticket = mint_ws_ticket({"actor": "tester", "role": "admin"})

    tampered = ticket[:-4] + ("AAAA" if ticket[-4:] != "AAAA" else "BBBB")

    assert validate_ws_ticket(tampered) is None


def test_ws_ticket_rejects_garbage_input():
    assert validate_ws_ticket("not-a-real-ticket") is None
    assert validate_ws_ticket("") is None


def test_ws_ticket_expires(monkeypatch):
    monkeypatch.setenv("SVOS_OPERATOR_TOKEN", "secret-token")
    # ttl_seconds is floored at 5 inside mint_ws_ticket — request 1s to prove
    # the floor doesn't silently disable expiry, then wait past the floor.
    ticket = mint_ws_ticket({"actor": "tester", "role": "admin"}, ttl_seconds=1)

    assert validate_ws_ticket(ticket) is not None  # not yet expired

    ticket2 = mint_ws_ticket({"actor": "tester2", "role": "admin"}, ttl_seconds=1)
    time.sleep(5.5)

    assert validate_ws_ticket(ticket2) is None  # past the 5s floor


def test_ws_ticket_signed_with_different_secret_is_rejected(monkeypatch):
    """A ticket minted under one operator-token generation must not validate
    after the token rotates — proves the signature is actually load-bearing,
    not just present."""
    monkeypatch.setenv("SVOS_OPERATOR_TOKEN", "secret-token-v1")
    ticket = mint_ws_ticket({"actor": "tester", "role": "admin"})

    monkeypatch.setenv("SVOS_OPERATOR_TOKEN", "secret-token-v2")

    assert validate_ws_ticket(ticket) is None
