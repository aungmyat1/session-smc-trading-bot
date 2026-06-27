"""Tests for the system health check helpers."""

from __future__ import annotations

import scripts.health_check as health_check


def test_postgres_backend_is_critical_when_unavailable(monkeypatch):
    monkeypatch.setattr(health_check, "_postgres_service_status", lambda: "active")

    def _refuse(*args, **kwargs):
        raise ConnectionRefusedError(111, "Connection refused")

    monkeypatch.setattr(health_check.socket, "create_connection", _refuse)

    result = health_check.check_research_db("postgres")

    assert result["status"] == "FAIL"
    assert "required=True" in result["detail"]
    assert "127.0.0.1:5432" in result["detail"] or "localhost:5432" in result["detail"]


def test_disabled_backend_skips_db_probe(monkeypatch):
    monkeypatch.setenv("DB_BACKEND", "disabled")

    def _should_not_be_called(*args, **kwargs):
        raise AssertionError("socket.create_connection should not run in disabled mode")

    monkeypatch.setattr(health_check.socket, "create_connection", _should_not_be_called)

    result = health_check.check_research_db()

    assert result["status"] == "SKIP"
    assert "disabled" in result["detail"].lower()


def test_duckdb_mode_does_not_probe_localhost(monkeypatch):
    monkeypatch.delenv("DB_BACKEND", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(health_check, "_load_yaml", lambda _path: {"analytics": {"duckdb_path": "research.db"}})

    def _should_not_be_called(*args, **kwargs):
        raise AssertionError("socket.create_connection should not run for DuckDB mode")

    monkeypatch.setattr(health_check.socket, "create_connection", _should_not_be_called)

    result = health_check.check_research_db()

    assert result["status"] == "SKIP"
    assert "duckdb" in result["detail"].lower()


def test_database_url_postgres_takes_precedence_over_duckdb_config(monkeypatch):
    monkeypatch.delenv("DB_BACKEND", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@db.example:5432/research")
    monkeypatch.setattr(health_check, "_load_yaml", lambda _path: {"analytics": {"duckdb_path": "research.db"}})
    monkeypatch.setattr(health_check, "_postgres_service_status", lambda: "active")
    monkeypatch.setattr(health_check.socket, "create_connection", lambda *args, **kwargs: _FakeSocket())

    backend, meta = health_check._infer_db_backend()

    assert backend == "postgres"
    assert meta["database_url"].startswith("postgresql://")


def test_missing_db_config_fails_closed(monkeypatch):
    monkeypatch.delenv("DB_BACKEND", raising=False)
    monkeypatch.delenv("DB_HEALTHCHECK_ENABLED", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("DB_HOST", raising=False)
    monkeypatch.delenv("DB_PORT", raising=False)
    monkeypatch.delenv("DB_NAME", raising=False)
    monkeypatch.setattr(health_check, "_load_yaml", lambda _path: {})

    result = health_check.check_research_db()

    assert result["status"] == "FAIL"
    assert "missing database runtime config" in result["detail"].lower()
