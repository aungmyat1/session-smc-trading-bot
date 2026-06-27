from __future__ import annotations

import os

_DEFAULT_DASHBOARD_HOST = "0.0.0.0"


def dashboard_bind_host() -> str:
    host = os.getenv("DASHBOARD_HOST", "").strip()
    if host:
        return host
    host = os.getenv("VPS_IP_ADDRESS", "").strip()
    if host:
        return host
    return _DEFAULT_DASHBOARD_HOST


def dashboard_public_host(bind_host: str | None = None) -> str:
    host = os.getenv("DASHBOARD_PUBLIC_HOST", "").strip()
    if host:
        return host
    host = os.getenv("VPS_IP_ADDRESS", "").strip()
    if host:
        return host
    host = (bind_host or "").strip()
    if host in {"0.0.0.0", "::", ""}:
        return "localhost"
    return host


def dashboard_url(host: str, port: int) -> str:
    return f"http://{host}:{port}"
