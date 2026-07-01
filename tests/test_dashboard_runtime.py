from __future__ import annotations

from dashboard.runtime import (
    dashboard_bind_host,
    dashboard_public_host,
    dashboard_url,
    live_dashboard_bind_host,
    live_dashboard_port,
    live_dashboard_public_host,
)


def test_dashboard_bind_host_prefers_explicit_host(monkeypatch):
    monkeypatch.setenv("DASHBOARD_HOST", "203.0.113.10")
    monkeypatch.delenv("VPS_IP_ADDRESS", raising=False)
    assert dashboard_bind_host() == "203.0.113.10"


def test_dashboard_bind_host_falls_back_to_vps_ip(monkeypatch):
    monkeypatch.delenv("DASHBOARD_HOST", raising=False)
    monkeypatch.setenv("VPS_IP_ADDRESS", "203.0.113.10")
    assert dashboard_bind_host() == "203.0.113.10"


def test_dashboard_bind_host_falls_back_to_0000(monkeypatch):
    monkeypatch.delenv("DASHBOARD_HOST", raising=False)
    monkeypatch.delenv("VPS_IP_ADDRESS", raising=False)
    assert dashboard_bind_host() == "0.0.0.0"


def test_dashboard_public_host_uses_vps_ip(monkeypatch):
    monkeypatch.delenv("DASHBOARD_PUBLIC_HOST", raising=False)
    monkeypatch.setenv("VPS_IP_ADDRESS", "203.0.113.10")
    assert dashboard_public_host("0.0.0.0") == "203.0.113.10"


def test_dashboard_public_host_explicit_override(monkeypatch):
    monkeypatch.setenv("DASHBOARD_PUBLIC_HOST", "my.domain.com")
    monkeypatch.setenv("VPS_IP_ADDRESS", "203.0.113.10")
    assert dashboard_public_host("0.0.0.0") == "my.domain.com"


def test_dashboard_public_host_bind_passthrough(monkeypatch):
    monkeypatch.delenv("DASHBOARD_PUBLIC_HOST", raising=False)
    monkeypatch.delenv("VPS_IP_ADDRESS", raising=False)
    assert dashboard_public_host("10.0.0.1") == "10.0.0.1"


def test_dashboard_public_host_wildcard_becomes_localhost(monkeypatch):
    monkeypatch.delenv("DASHBOARD_PUBLIC_HOST", raising=False)
    monkeypatch.delenv("VPS_IP_ADDRESS", raising=False)
    assert dashboard_public_host("0.0.0.0") == "localhost"
    assert dashboard_public_host("::") == "localhost"
    assert dashboard_public_host("") == "localhost"


def test_dashboard_url_formats_host_and_port():
    assert dashboard_url("203.0.113.10", 8080) == "http://203.0.113.10:8080"


def test_dashboard_url_non_standard_port():
    assert dashboard_url("localhost", 9090) == "http://localhost:9090"


def test_live_dashboard_bind_host_prefers_explicit_value(monkeypatch):
    monkeypatch.setenv("LIVE_DASHBOARD_HOST", "198.51.100.44")
    monkeypatch.setenv("DASHBOARD_HOST", "203.0.113.10")
    assert live_dashboard_bind_host() == "198.51.100.44"


def test_live_dashboard_bind_host_falls_back_to_dashboard_host(monkeypatch):
    monkeypatch.delenv("LIVE_DASHBOARD_HOST", raising=False)
    monkeypatch.setenv("DASHBOARD_HOST", "203.0.113.10")
    assert live_dashboard_bind_host() == "203.0.113.10"


def test_live_dashboard_public_host_prefers_explicit_value(monkeypatch):
    monkeypatch.setenv("LIVE_DASHBOARD_PUBLIC_HOST", "live.example.com")
    assert live_dashboard_public_host("0.0.0.0") == "live.example.com"


def test_live_dashboard_public_host_falls_back_to_dashboard_public_host(monkeypatch):
    monkeypatch.delenv("LIVE_DASHBOARD_PUBLIC_HOST", raising=False)
    monkeypatch.delenv("DASHBOARD_PUBLIC_HOST", raising=False)
    monkeypatch.setenv("VPS_IP_ADDRESS", "203.0.113.10")
    assert live_dashboard_public_host("0.0.0.0") == "203.0.113.10"


def test_live_dashboard_port_defaults_to_8090(monkeypatch):
    monkeypatch.delenv("LIVE_DASHBOARD_PORT", raising=False)
    assert live_dashboard_port() == 8090


def test_live_dashboard_port_respects_override(monkeypatch):
    monkeypatch.setenv("LIVE_DASHBOARD_PORT", "8181")
    assert live_dashboard_port() == 8181
