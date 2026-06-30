"""Tests for the system health check helpers."""

from __future__ import annotations

import scripts.health_check as health_check


def test_postgres_backend_is_critical_when_unavailable(monkeypatch):
    monkeypatch.setattr(health_check, "_postgres_service_status", lambda: "active")
    monkeypatch.setattr(
        health_check, "_record_db_probe_result", lambda endpoint_key, ok: 3
    )

    def _refuse(*args, **kwargs):
        raise ConnectionRefusedError(111, "Connection refused")

    monkeypatch.setattr(
        health_check,
        "_probe_socket",
        lambda host, port: (
            False,
            "ConnectionRefusedError: [Errno 111] Connection refused",
        ),
    )

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
    monkeypatch.setattr(
        health_check,
        "_load_yaml",
        lambda _path: {"analytics": {"duckdb_path": "research.db"}},
    )

    def _should_not_be_called(*args, **kwargs):
        raise AssertionError("socket.create_connection should not run for DuckDB mode")

    monkeypatch.setattr(health_check.socket, "create_connection", _should_not_be_called)

    result = health_check.check_research_db()

    assert result["status"] == "SKIP"
    assert "duckdb" in result["detail"].lower()


def test_database_url_postgres_takes_precedence_over_duckdb_config(monkeypatch):
    monkeypatch.delenv("DB_BACKEND", raising=False)
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql://user:pass@db.example:5432/research"
    )
    monkeypatch.setattr(
        health_check,
        "_load_yaml",
        lambda _path: {"analytics": {"duckdb_path": "research.db"}},
    )
    monkeypatch.setattr(health_check, "_postgres_service_status", lambda: "active")
    monkeypatch.setattr(
        health_check, "_probe_socket", lambda host, port: (True, "reachable")
    )

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


def test_postgres_backend_warns_before_failure_threshold(monkeypatch):
    monkeypatch.setattr(health_check, "_postgres_service_status", lambda: "active")
    monkeypatch.setattr(
        health_check, "_record_db_probe_result", lambda endpoint_key, ok: 1
    )
    monkeypatch.setattr(
        health_check,
        "_probe_socket",
        lambda host, port: (
            False,
            "ConnectionRefusedError: [Errno 111] Connection refused",
        ),
    )

    result = health_check.check_research_db("postgres")

    assert result["status"] == "WARN"
    assert result["consecutive_failures"] == 1
    assert result["alert_eligible"] is False


def test_localhost_in_container_warns_if_fallback_host_is_reachable(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@127.0.0.1:5432/research")
    monkeypatch.setattr(health_check, "_postgres_service_status", lambda: "unknown")
    monkeypatch.setattr(health_check, "_in_container_runtime", lambda: True)
    monkeypatch.setattr(
        health_check, "_record_db_probe_result", lambda endpoint_key, ok: 0
    )

    def _probe(host, port):
        if host == "127.0.0.1":
            return False, "ConnectionRefusedError: [Errno 111] Connection refused"
        if host == "host.docker.internal":
            return True, "reachable"
        return False, "not reached"

    monkeypatch.setattr(health_check, "_probe_socket", _probe)

    result = health_check.check_research_db("postgres")

    assert result["status"] == "WARN"
    assert result["configured_host"] == "127.0.0.1"
    assert result["effective_host"] == "host.docker.internal"


def test_recovery_check_reports_loaded_state_and_journal(tmp_path, monkeypatch):
    monkeypatch.setattr(health_check, "_ROOT", tmp_path)
    logs = tmp_path / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    (logs / "bot_state.json").write_text(
        '{"daily_loss_r": 1.5, "weekly_loss_r": 2.0, "consecutive_losses": 2, "halted": false}',
        encoding="utf-8",
    )
    (logs / "trades.jsonl").write_text(
        "\n".join(
            [
                '{"event":"SIGNAL_CREATED"}',
                '{"event":"ORDER_SUBMITTED"}',
                '{"event":"ORDER_FILLED"}',
                '{"event":"POSITION_CLOSED"}',
            ]
        ),
        encoding="utf-8",
    )

    result = health_check.check_recovery()

    assert result["status"] == "PASS"
    assert result["journal"]["signals"] == 1
    assert result["journal"]["closes"] == 1


def test_recovery_check_warns_when_no_artifacts(tmp_path, monkeypatch):
    monkeypatch.setattr(health_check, "_ROOT", tmp_path)
    result = health_check.check_recovery()
    assert result["status"] == "WARN"
    assert "no restart recovery state" in result["detail"].lower()


def test_emergency_stop_blocks_risk_engine(tmp_path, monkeypatch):
    monkeypatch.setattr(
        health_check, "_CONTROL_STATE_PATH", tmp_path / "reports" / "control_state.json"
    )
    (tmp_path / "reports").mkdir(parents=True, exist_ok=True)
    (tmp_path / "reports" / "control_state.json").write_text(
        '{"emergency_stop":{"active":true,"reason":"operator halt"}}',
        encoding="utf-8",
    )

    result = health_check.check_risk_engine()

    assert result["status"] == "FAIL"
    assert "EMERGENCY_STOP" in result["detail"]


def test_emergency_stop_blocks_execution(tmp_path, monkeypatch):
    monkeypatch.setattr(
        health_check, "_CONTROL_STATE_PATH", tmp_path / "reports" / "control_state.json"
    )
    (tmp_path / "reports").mkdir(parents=True, exist_ok=True)
    (tmp_path / "reports" / "control_state.json").write_text(
        '{"emergency_stop":{"active":true,"reason":"operator halt"}}',
        encoding="utf-8",
    )

    result = health_check.check_execution()

    assert result["status"] == "BLOCKED"
    assert "EMERGENCY_STOP" in result["detail"]
