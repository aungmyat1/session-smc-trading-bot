from __future__ import annotations

import hmac
import os
import secrets
from datetime import datetime, timezone
from functools import wraps
from urllib.parse import urlsplit

from flask import jsonify, request

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

_ROLE_ACTIONS = {
    "research_operator": {
        "reports:review",
        "reports:generate",
    },
    "incident_operator": {
        "incidents:ack",
    },
    "risk_operator": {
        "positions:close",
        "positions:protect",
        "orders:cancel",
        "emergency_stop:activate",
        "deployments:create",
        "deployments:import",
        "deployments:preflight",
        "deployments:activate",
        "deployments:rollback",
    },
    "admin": {
        "positions:close",
        "positions:protect",
        "orders:cancel",
        "emergency_stop:activate",
        "emergency_stop:clear",
        "deployments:create",
        "deployments:import",
        "deployments:preflight",
        "deployments:activate",
        "deployments:rollback",
        "reports:review",
        "reports:generate",
        "incidents:ack",
    },
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _error(message: str, status: int, **extra):
    return jsonify({"error": message, "fetched_at": _now_iso(), **extra}), status


def _configured_token(app) -> str:
    return str(app.config.get("SVOS_OPERATOR_TOKEN") or os.getenv("SVOS_OPERATOR_TOKEN", "")).strip()


def _proxy_secret(app) -> str:
    return str(app.config.get("DASHBOARD_PROXY_SECRET") or os.getenv("DASHBOARD_PROXY_SECRET", "")).strip()


def _proxy_header_name(app, config_key: str, env_key: str, default: str) -> str:
    return str(app.config.get(config_key) or os.getenv(env_key, default)).strip() or default


def _same_origin() -> bool:
    origin = request.headers.get("Origin", "").strip()
    referer = request.headers.get("Referer", "").strip()
    source = origin or referer
    if not source:
        return False
    source_parts = urlsplit(source)
    host_parts = urlsplit(request.host_url)
    return (
        source_parts.scheme == host_parts.scheme
        and source_parts.netloc == host_parts.netloc
    )


def _resolve_identity(app) -> dict[str, str] | None:
    proxy_secret = _proxy_secret(app)
    proxy_secret_header = _proxy_header_name(
        app,
        "DASHBOARD_PROXY_SECRET_HEADER",
        "DASHBOARD_PROXY_SECRET_HEADER",
        "X-Dashboard-Proxy-Secret",
    )
    proxy_actor_header = _proxy_header_name(
        app,
        "DASHBOARD_PROXY_ACTOR_HEADER",
        "DASHBOARD_PROXY_ACTOR_HEADER",
        "X-Forwarded-Email",
    )
    proxy_role_header = _proxy_header_name(
        app,
        "DASHBOARD_PROXY_ROLE_HEADER",
        "DASHBOARD_PROXY_ROLE_HEADER",
        "X-SVOS-Proxy-Role",
    )

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

    configured = _configured_token(app)
    supplied = request.headers.get("Authorization", "").strip()
    actor = request.headers.get("X-SVOS-Actor", "").strip()
    role = request.headers.get("X-SVOS-Role", "").strip()
    expected = f"Bearer {configured}" if configured else ""
    if configured and supplied and hmac.compare_digest(supplied, expected) and actor and role:
        return {"actor": actor, "role": role, "auth_mode": "bearer"}
    return None


def _permitted_actions(role: str) -> list[str]:
    actions = set(_ROLE_ACTIONS.get(role, set()))
    if role == "admin":
        for value in _ROLE_ACTIONS.values():
            actions.update(value)
    return sorted(actions)


def build_session_payload(app) -> dict[str, object]:
    identity = _resolve_identity(app)
    live_trading_enabled = _env_bool("LIVE_TRADING", False)
    demo_only = _env_bool("DEMO_ONLY", True)
    trading_mode = "live" if live_trading_enabled else ("demo" if demo_only else "paper")

    if identity is None:
        return {
            "authenticated": False,
            "actor": "",
            "role": "",
            "auth_mode": "",
            "permitted_actions": [],
            "mutation_allowed": False,
            "trading_mode": trading_mode,
            "demo_only": demo_only,
            "live_trading_enabled": live_trading_enabled,
        }

    role = str(identity["role"])
    return {
        "authenticated": True,
        "actor": str(identity["actor"]),
        "role": role,
        "auth_mode": str(identity["auth_mode"]),
        "permitted_actions": _permitted_actions(role),
        "mutation_allowed": role in _ROLE_ACTIONS,
        "trading_mode": trading_mode,
        "demo_only": demo_only,
        "live_trading_enabled": live_trading_enabled,
    }


def ensure_csrf_cookie(response) -> None:
    cookie_name = os.getenv("DASHBOARD_CSRF_COOKIE_NAME", "dashboard_csrf").strip() or "dashboard_csrf"
    if request.cookies.get(cookie_name):
        return
    response.set_cookie(
        cookie_name,
        secrets.token_urlsafe(24),
        secure=request.is_secure,
        httponly=False,
        samesite="Lax",
        path="/",
    )


def require_operator(app, *allowed_roles: str):
    """Require a trusted operator identity via bearer token or trusted proxy."""

    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            payload = build_session_payload(app)
            if not payload["authenticated"]:
                configured = bool(_configured_token(app))
                proxy_ready = bool(_proxy_secret(app))
                if not configured and not proxy_ready:
                    return _error("Operator authentication is not configured", 503, code="auth_not_configured")
                return _error("Unauthorized", 401, code="unauthorized")

            role = str(payload["role"])
            if role not in allowed_roles:
                return _error("Forbidden", 403, code="forbidden", required_roles=list(allowed_roles))

            if payload["auth_mode"] == "proxy" and request.method not in SAFE_METHODS:
                if not _same_origin():
                    return _error("Rejected unsafe cross-origin mutation", 403, code="csrf_origin_mismatch")
                cookie_name = os.getenv("DASHBOARD_CSRF_COOKIE_NAME", "dashboard_csrf").strip() or "dashboard_csrf"
                header_name = os.getenv("DASHBOARD_CSRF_HEADER_NAME", "X-CSRF-Token").strip() or "X-CSRF-Token"
                cookie_value = request.cookies.get(cookie_name, "")
                header_value = request.headers.get(header_name, "").strip()
                if not cookie_value or not header_value or not hmac.compare_digest(header_value, cookie_value):
                    return _error("Missing or invalid CSRF token", 403, code="csrf_failed")

            request.environ["svos.actor"] = str(payload["actor"])
            request.environ["svos.role"] = role
            request.environ["svos.auth_mode"] = str(payload["auth_mode"])
            return view(*args, **kwargs)

        return wrapped

    return decorator
