"""
FastAPI-native operator authentication for dashboard/status_server.py.

dashboard/auth.py already implements the real identity/role/permission model
(bearer token or trusted-reverse-proxy headers, role -> permitted-actions
mapping) but is written against Flask's request/jsonify globals — it cannot
be imported directly into this FastAPI app. Rather than inventing a second,
divergent role model, this module reuses dashboard.auth's actual data
(_ROLE_ACTIONS, _permitted_actions) and env-var configuration
(SVOS_OPERATOR_TOKEN, DASHBOARD_PROXY_SECRET, header names) so one operator
credential works identically whether it hits app.py/live_app.py (Flask) or
status_server.py (FastAPI, this file).

Public API:
    resolve_identity(request: fastapi.Request) -> dict | None
    require_role(*allowed_roles: str) -> FastAPI dependency
    mint_ws_ticket(identity: dict) -> str
    validate_ws_ticket(ticket: str) -> dict | None

WebSocket ticket auth (2026-07-05): browsers cannot set Authorization/
X-SVOS-Actor headers on a WebSocket upgrade request, so the header-based
model above is structurally unusable for a browser-initiated /ws connection.
mint_ws_ticket()/validate_ws_ticket() add a short-lived (30s), single-use,
HMAC-signed ticket that a caller obtains via a normal, fully-authenticated
REST call (GET /api/ws-ticket, gated by require_authenticated() same as any
other read endpoint) and then passes as a query parameter on the WS URL —
the one place a browser *can* attach a credential. This does not add a new
way to authenticate; it only carries an already-established identity onto
one transport that can't carry headers. Header-based auth on /ws itself is
preserved unchanged as a fallback for any non-browser caller that already
uses it.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from datetime import datetime, timezone
from typing import Any

from urllib.parse import urlsplit

from fastapi import HTTPException, Request

from dashboard.auth import _ROLE_ACTIONS, _permitted_actions

_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
_WS_TICKET_TTL_SECONDS = 30
_used_ws_ticket_nonces: dict[str, float] = {}  # nonce -> expiry epoch, pruned lazily on each validation


def _same_origin(request: Request) -> bool:
    origin = request.headers.get("Origin", "").strip()
    referer = request.headers.get("Referer", "").strip()
    source = origin or referer
    if not source:
        return False
    source_parts = urlsplit(source)
    forwarded_proto = request.headers.get("X-Forwarded-Proto", "").strip()
    forwarded_host = request.headers.get("X-Forwarded-Host", "").strip()
    expected_scheme = forwarded_proto or request.url.scheme
    expected_host = forwarded_host or request.headers.get("host", "")
    host_parts = urlsplit(f"{expected_scheme}://{expected_host}")
    return source_parts.scheme == host_parts.scheme and source_parts.netloc == host_parts.netloc

_env_bool = lambda name, default: os.getenv(name, "").strip().lower() in ("1", "true", "yes", "on") if os.getenv(name) is not None else default  # noqa: E731


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _configured_token() -> str:
    return os.getenv("SVOS_OPERATOR_TOKEN", "").strip()


def _proxy_secret() -> str:
    return os.getenv("DASHBOARD_PROXY_SECRET", "").strip()


def _bearer_role() -> str:
    """Fixed server-side role granted to holders of SVOS_OPERATOR_TOKEN.

    Bearer tokens are a single shared operator credential, so the role they
    grant must be assigned by the server, never taken from a caller-supplied
    header — otherwise anyone holding the token could self-declare "admin".
    X-SVOS-Role is honored only in proxy mode, where it's already gated by a
    trusted-proxy secret the caller cannot forge.
    """
    return os.getenv("SVOS_OPERATOR_ROLE", "admin").strip() or "admin"


def _ws_ticket_secret() -> bytes:
    """HMAC key for WS connection tickets. Reuses whichever operator
    credential material is already configured (bearer token, else proxy
    secret) rather than provisioning a third secret — if neither is
    configured, require_authenticated() already rejects everyone, so ticket
    issuance is unreachable and never exercised against real traffic in
    that case."""
    material = _configured_token() or _proxy_secret() or "unconfigured-ws-ticket-secret"
    return material.encode("utf-8")


def _prune_used_ws_ticket_nonces() -> None:
    now = time.time()
    for nonce in [n for n, exp in _used_ws_ticket_nonces.items() if exp < now]:
        del _used_ws_ticket_nonces[nonce]


def mint_ws_ticket(identity: dict[str, str], ttl_seconds: int = _WS_TICKET_TTL_SECONDS) -> str:
    """Mint a short-lived, single-use, signed ticket carrying an already-
    authenticated identity onto the /ws handshake. Caller must already have
    passed require_authenticated() — see module docstring."""
    payload = {
        "actor": identity["actor"],
        "role": identity["role"],
        "exp": int(time.time()) + max(5, ttl_seconds),
        "nonce": secrets.token_urlsafe(16),
    }
    payload_json = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    sig = hmac.new(_ws_ticket_secret(), payload_json.encode("utf-8"), hashlib.sha256).hexdigest()
    return base64.urlsafe_b64encode(json.dumps({"p": payload_json, "s": sig}).encode("utf-8")).decode("ascii")


def validate_ws_ticket(ticket: str) -> dict[str, str] | None:
    """Validate signature, expiry, and single-use of a mint_ws_ticket() token.
    Returns an identity dict shaped like resolve_identity()'s on success."""
    try:
        token = json.loads(base64.urlsafe_b64decode(ticket.encode("ascii")).decode("utf-8"))
        payload_json, sig = str(token["p"]), str(token["s"])
    except Exception:
        return None
    expected_sig = hmac.new(_ws_ticket_secret(), payload_json.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected_sig):
        return None
    try:
        payload = json.loads(payload_json)
        actor, role, exp, nonce = str(payload["actor"]), str(payload["role"]), int(payload["exp"]), str(payload["nonce"])
    except Exception:
        return None
    if exp < time.time():
        return None
    _prune_used_ws_ticket_nonces()
    if nonce in _used_ws_ticket_nonces:
        return None  # already used once — replay rejected
    _used_ws_ticket_nonces[nonce] = exp
    return {"actor": actor, "role": role, "auth_mode": "ws-ticket"}


def resolve_identity(request: Request) -> dict[str, str] | None:
    """Same precedence as dashboard/auth.py: trusted-proxy headers first
    (if a proxy secret is configured and matches), then a bearer token."""
    proxy_secret = _proxy_secret()
    proxy_secret_header = os.getenv("DASHBOARD_PROXY_SECRET_HEADER", "X-Dashboard-Proxy-Secret").strip()
    proxy_actor_header = os.getenv("DASHBOARD_PROXY_ACTOR_HEADER", "X-Forwarded-Email").strip()
    proxy_role_header = os.getenv("DASHBOARD_PROXY_ROLE_HEADER", "X-SVOS-Proxy-Role").strip()

    supplied_secret = request.headers.get(proxy_secret_header, "").strip()
    proxy_actor = request.headers.get(proxy_actor_header, "").strip()
    proxy_role = request.headers.get(proxy_role_header, "").strip()
    if proxy_actor or proxy_role or supplied_secret:
        if not proxy_secret:
            return None
        if not supplied_secret or not hmac.compare_digest(supplied_secret, proxy_secret):
            return None
        if not proxy_actor or not proxy_role:
            return None
        return {"actor": proxy_actor, "role": proxy_role, "auth_mode": "proxy"}

    configured = _configured_token()
    supplied = request.headers.get("Authorization", "").strip()
    actor = request.headers.get("X-SVOS-Actor", "").strip()
    expected = f"Bearer {configured}" if configured else ""
    if configured and supplied and hmac.compare_digest(supplied, expected) and actor:
        return {"actor": actor, "role": _bearer_role(), "auth_mode": "bearer"}
    return None


def session_payload(request: Request) -> dict[str, Any]:
    identity = resolve_identity(request)
    live_trading_enabled = _env_bool("LIVE_TRADING", False)
    demo_only = _env_bool("DEMO_ONLY", True)
    trading_mode = "live" if live_trading_enabled else ("demo" if demo_only else "paper")
    if identity is None:
        return {
            "authenticated": False, "actor": "", "role": "", "auth_mode": "",
            "permitted_actions": [], "mutation_allowed": False,
            "trading_mode": trading_mode, "demo_only": demo_only, "live_trading_enabled": live_trading_enabled,
        }
    role = str(identity["role"])
    return {
        "authenticated": True, "actor": str(identity["actor"]), "role": role,
        "auth_mode": str(identity["auth_mode"]), "permitted_actions": _permitted_actions(role),
        "mutation_allowed": role in _ROLE_ACTIONS,
        "trading_mode": trading_mode, "demo_only": demo_only, "live_trading_enabled": live_trading_enabled,
    }


def _require_authenticated_payload(request: Request) -> dict[str, Any]:
    """Shared 401/503 gate: raise unless the caller has ANY valid operator
    identity. Used both by require_role() (which additionally checks role)
    and require_authenticated() (read-only endpoints — any operator identity
    may read, regardless of role)."""
    payload = session_payload(request)
    if not payload["authenticated"]:
        configured = bool(_configured_token())
        proxy_ready = bool(_proxy_secret())
        if not configured and not proxy_ready:
            raise HTTPException(status_code=503, detail={"error": "Operator authentication is not configured", "code": "auth_not_configured"})
        raise HTTPException(status_code=401, detail={"error": "Unauthorized", "code": "unauthorized"})
    return payload


def require_authenticated():
    """FastAPI dependency: raises 401/503 unless the caller has ANY valid
    operator identity — for read-only endpoints that must not be reachable
    anonymously but aren't restricted to specific mutation roles."""

    def dependency(request: Request) -> dict[str, Any]:
        return _require_authenticated_payload(request)

    return dependency


def require_role(*allowed_roles: str):
    """FastAPI dependency: raises 401/403 unless the caller authenticates as
    one of allowed_roles. Use as: Depends(require_role("risk_operator", "admin"))."""

    def dependency(request: Request) -> dict[str, Any]:
        payload = _require_authenticated_payload(request)
        role = str(payload["role"])
        if role not in allowed_roles:
            raise HTTPException(status_code=403, detail={"error": "Forbidden", "code": "forbidden", "required_roles": list(allowed_roles)})

        if payload["auth_mode"] == "proxy" and request.method not in _SAFE_METHODS:
            if not _same_origin(request):
                raise HTTPException(status_code=403, detail={"error": "Rejected unsafe cross-origin mutation", "code": "csrf_origin_mismatch"})
            cookie_name = os.getenv("DASHBOARD_CSRF_COOKIE_NAME", "dashboard_csrf").strip() or "dashboard_csrf"
            header_name = os.getenv("DASHBOARD_CSRF_HEADER_NAME", "X-CSRF-Token").strip() or "X-CSRF-Token"
            cookie_value = request.cookies.get(cookie_name, "")
            header_value = request.headers.get(header_name, "").strip()
            if not cookie_value or not header_value or not hmac.compare_digest(header_value, cookie_value):
                raise HTTPException(status_code=403, detail={"error": "Missing or invalid CSRF token", "code": "csrf_failed"})

        return payload

    return dependency
