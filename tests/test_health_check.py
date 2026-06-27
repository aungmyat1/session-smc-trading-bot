"""Tests for the system health check helpers."""

from __future__ import annotations

import scripts.health_check as health_check


class _FakeSocket:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_research_db_check_pass(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@db.example:5432/research")
    monkeypatch.setattr(health_check.socket, "create_connection", lambda *args, **kwargs: _FakeSocket())

    result = health_check.check_research_db()

    assert result["status"] == "PASS"
    assert "db.example:5432" in result["detail"]


def test_research_db_check_warn_on_refusal(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@127.0.0.1:5432/research")

    def _refuse(*args, **kwargs):
        raise ConnectionRefusedError(111, "Connection refused")

    monkeypatch.setattr(health_check.socket, "create_connection", _refuse)

    result = health_check.check_research_db()

    assert result["status"] == "WARN"
    assert "127.0.0.1:5432" in result["detail"]
