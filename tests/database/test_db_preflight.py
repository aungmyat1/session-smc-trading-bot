"""Tests for scripts/db_preflight.py — database preflight verification."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.db_preflight import (
    PreflightError,
    check_env,
    check_connectivity,
    check_schemas,
    check_system2_tables,
    check_permissions,
    check_alembic,
    check_system_resources,
    main,
    run_preflight,
    _ALL_REQUIRED_SCHEMAS,
    _SYSTEM2_OPERATIONS_TABLES,
)

# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

MOCK_DATABASE_URL = "postgresql://test_user:test_pass@localhost:15432/svos_test"


@pytest.fixture(autouse=True)
def clear_env() -> None:
    """Remove DATABASE_URL before each test so tests control their env."""
    if "DATABASE_URL" in os.environ:
        del os.environ["DATABASE_URL"]


@pytest.fixture
def mock_sqlalchemy_engine() -> MagicMock:
    """Return a mock engine that always succeeds."""
    engine = MagicMock()
    conn = MagicMock()
    result = MagicMock()
    result.fetchone.return_value = (1,)
    result.fetchall.return_value = []
    conn.execute.return_value = result
    conn.__enter__.return_value = conn
    conn.__exit__.return_value = None
    engine.connect.return_value = conn
    return engine


# ═══════════════════════════════════════════════════════════════════════════════
# check_env
# ═══════════════════════════════════════════════════════════════════════════════

def test_env_missing_raises() -> None:
    with pytest.raises(PreflightError) as exc:
        check_env()
    assert exc.value.token == "missing_env"


def test_env_empty_raises() -> None:
    os.environ["DATABASE_URL"] = ""
    with pytest.raises(PreflightError) as exc:
        check_env()
    assert exc.value.token == "missing_env"


def test_env_valid_returns_normalized_url() -> None:
    os.environ["DATABASE_URL"] = MOCK_DATABASE_URL
    result = check_env()
    assert "database_url" in result
    assert result["database_url"] == MOCK_DATABASE_URL


def test_env_normalizes_asyncpg_url() -> None:
    async_url = "postgresql+asyncpg://user:pass@localhost:5432/svos"
    os.environ["DATABASE_URL"] = async_url
    result = check_env()
    assert result["database_url"].startswith("postgresql://")
    assert "+asyncpg" not in result["database_url"]


# ═══════════════════════════════════════════════════════════════════════════════
# check_alembic — uses subprocess mock
# ═══════════════════════════════════════════════════════════════════════════════

def test_alembic_current_matches_head() -> None:
    """Simulate alembic current = alembic heads."""
    def fake_run(*args, **kwargs):  # noqa: ANN401
        cmd = args[0] if args else kwargs.get("args", [])
        mock = MagicMock()
        # cmd will look like ['python3', '-m', 'alembic', 'current']
        if "current" in cmd:
            mock.stdout = "004abc (head)\n"
        elif "heads" in cmd:
            mock.stdout = "004abc\n"
        else:
            mock.stdout = ""
        mock.returncode = 0
        return mock

    with patch("scripts.db_preflight.subprocess.run", fake_run):
        result = check_alembic()
    assert result["match"] is True
    assert result["current_revision"] == "004abc"
    assert result["head_revision"] == "004abc"


def test_alembic_current_mismatch_head() -> None:
    def fake_run(*args, **kwargs):  # noqa: ANN401
        cmd = args[0] if args else kwargs.get("args", [])
        mock = MagicMock()
        if "current" in cmd:
            mock.stdout = "003abc\n"
        elif "heads" in cmd:
            mock.stdout = "004abc\n"
        else:
            mock.stdout = ""
        mock.returncode = 0
        return mock

    with patch("scripts.db_preflight.subprocess.run", fake_run):
        with pytest.raises(PreflightError) as exc:
            check_alembic()
    assert exc.value.token == "migration_mismatch"


def test_alembic_no_current_revision() -> None:
    """Empty database — no migrations applied yet."""
    def fake_run(*args, **kwargs):  # noqa: ANN401
        cmd = args[0] if args else kwargs.get("args", [])
        mock = MagicMock()
        if "current" in cmd:
            mock.stdout = ""
        elif "heads" in cmd:
            mock.stdout = "004abc\n"
        else:
            mock.stdout = ""
        mock.returncode = 0
        return mock

    with patch("scripts.db_preflight.subprocess.run", fake_run):
        with pytest.raises(PreflightError) as exc:
            check_alembic()
    assert exc.value.token == "migration_mismatch"


# ═══════════════════════════════════════════════════════════════════════════════
# check_connectivity — uses mock SQLAlchemy engine
# ═══════════════════════════════════════════════════════════════════════════════

def test_connectivity_pass() -> None:
    with patch("scripts.db_preflight.create_engine") as mock_create:
        engine = MagicMock()
        conn = MagicMock()
        result = MagicMock()
        result.fetchone.return_value = (1,)
        conn.execute.return_value = result
        conn.__enter__.return_value = conn
        engine.connect.return_value = conn
        mock_create.return_value = engine

        result = check_connectivity(MOCK_DATABASE_URL)
        assert result["engine_ok"] is True


def test_connectivity_fail_select_1() -> None:
    with patch("scripts.db_preflight.create_engine") as mock_create:
        engine = MagicMock()
        conn = MagicMock()
        result = MagicMock()
        result.fetchone.return_value = (0,)
        conn.execute.return_value = result
        conn.__enter__.return_value = conn
        engine.connect.return_value = conn
        mock_create.return_value = engine

        with pytest.raises(PreflightError) as exc:
            check_connectivity(MOCK_DATABASE_URL)
        assert exc.value.token == "connection_failed"


def test_connectivity_fail_connection_error() -> None:
    with patch("scripts.db_preflight.create_engine") as mock_create:
        mock_create.side_effect = Exception("could not connect to server")

        with pytest.raises(PreflightError) as exc:
            check_connectivity(MOCK_DATABASE_URL)
        assert exc.value.token == "connection_failed"


# ═══════════════════════════════════════════════════════════════════════════════
# check_schemas
# ═══════════════════════════════════════════════════════════════════════════════

def test_schemas_all_present() -> None:
    with patch("scripts.db_preflight.create_engine") as mock_create:
        engine = MagicMock()
        conn = MagicMock()
        result = MagicMock()
        result.fetchall.return_value = [(s,) for s in _ALL_REQUIRED_SCHEMAS]
        conn.execute.return_value = result
        conn.__enter__.return_value = conn
        engine.connect.return_value = conn
        mock_create.return_value = engine

        result = check_schemas(MOCK_DATABASE_URL)
        assert result["all_present"] is True
        assert len(result["existing_schemas"]) >= len(_ALL_REQUIRED_SCHEMAS)


def test_schemas_missing_v3() -> None:
    with patch("scripts.db_preflight.create_engine") as mock_create:
        engine = MagicMock()
        conn = MagicMock()
        # Only v2 schemas present
        schema_list = [("market",), ("research",), ("analytics",)]
        result = MagicMock()
        result.fetchall.return_value = schema_list
        conn.execute.return_value = result
        conn.__enter__.return_value = conn
        engine.connect.return_value = conn
        mock_create.return_value = engine

        with pytest.raises(PreflightError) as exc:
            check_schemas(MOCK_DATABASE_URL)
        assert exc.value.token == "missing_schema"
        assert "strategy" in exc.value.message


def test_schemas_empty() -> None:
    with patch("scripts.db_preflight.create_engine") as mock_create:
        engine = MagicMock()
        conn = MagicMock()
        result = MagicMock()
        result.fetchall.return_value = []
        conn.execute.return_value = result
        conn.__enter__.return_value = conn
        engine.connect.return_value = conn
        mock_create.return_value = engine

        with pytest.raises(PreflightError) as exc:
            check_schemas(MOCK_DATABASE_URL)
        assert exc.value.token == "missing_schema"


# ═══════════════════════════════════════════════════════════════════════════════
# check_system2_tables
# ═══════════════════════════════════════════════════════════════════════════════

def test_system2_tables_all_present() -> None:
    with patch("scripts.db_preflight.create_engine") as mock_create:
        engine = MagicMock()
        conn = MagicMock()
        result = MagicMock()
        result.fetchall.return_value = [("operations", t) for t in _SYSTEM2_OPERATIONS_TABLES]
        conn.execute.return_value = result
        conn.__enter__.return_value = conn
        engine.connect.return_value = conn
        mock_create.return_value = engine

        result = check_system2_tables(MOCK_DATABASE_URL)
        assert result["all_present"] is True


def test_system2_tables_missing() -> None:
    with patch("scripts.db_preflight.create_engine") as mock_create:
        engine = MagicMock()
        conn = MagicMock()
        result = MagicMock()
        # Only runtime table exists
        result.fetchall.return_value = [("operations", "runtime")]
        conn.execute.return_value = result
        conn.__enter__.return_value = conn
        engine.connect.return_value = conn
        mock_create.return_value = engine

        with pytest.raises(PreflightError) as exc:
            check_system2_tables(MOCK_DATABASE_URL)
        assert exc.value.token == "missing_table"


# ═══════════════════════════════════════════════════════════════════════════════
# check_permissions
# ═══════════════════════════════════════════════════════════════════════════════

def test_permissions_read_write_ok() -> None:
    with patch("scripts.db_preflight.create_engine") as mock_create:
        engine = MagicMock()
        conn = MagicMock()
        user_result = MagicMock()
        user_result.fetchone.return_value = ("svos_app",)
        count_result = MagicMock()
        count_result.fetchone.return_value = (42,)

        def side_effect(sql):  # noqa: ANN001
            txt = str(sql.compile(compile_kwargs={"literal_binds": True})).lower()
            if "current_user" in txt:
                return user_result
            if "count" in txt:
                return count_result
            return MagicMock()

        conn_execute_mock = MagicMock(side_effect=side_effect)
        conn.execute = conn_execute_mock
        conn.__enter__.return_value = conn
        engine.connect.return_value = conn
        mock_create.return_value = engine

        result = check_permissions(MOCK_DATABASE_URL)
        assert result["read_write_ok"] is True
        assert result["current_user"] == "svos_app"


# ═══════════════════════════════════════════════════════════════════════════════
# check_system_resources
# ═══════════════════════════════════════════════════════════════════════════════

def test_system_resources_warn_only() -> None:
    """Should never raise PreflightError — resources are advisory only."""
    result = check_system_resources()
    assert isinstance(result, dict)
    assert "disk_ok" in result
    assert "ram_ok" in result


# ═══════════════════════════════════════════════════════════════════════════════
# Integration: run_preflight
# ═══════════════════════════════════════════════════════════════════════════════

def test_preflight_fails_closed_when_env_missing() -> None:
    result = run_preflight(quiet=True)
    assert result["status"] == "DB_NOT_READY"
    assert result["error_token"] == "missing_env"


def test_preflight_fails_with_empty_url() -> None:
    os.environ["DATABASE_URL"] = ""
    result = run_preflight(quiet=True)
    assert result["status"] == "DB_NOT_READY"
    assert result["error_token"] == "missing_env"


def test_preflight_connection_failure_reports_token() -> None:
    os.environ["DATABASE_URL"] = MOCK_DATABASE_URL
    with patch("scripts.db_preflight.check_connectivity") as mock_conn:
        mock_conn.side_effect = PreflightError("connection_failed", "cannot connect")
        with patch("scripts.db_preflight.check_alembic") as mock_alc:
            with patch("scripts.db_preflight.check_schemas") as mock_sch:
                with patch("scripts.db_preflight.check_system2_tables") as mock_s2:
                    with patch("scripts.db_preflight.check_permissions") as mock_perm:
                        with patch("scripts.db_preflight.check_system_resources") as mock_res:
                            result = run_preflight(quiet=True)
        assert result["status"] == "DB_NOT_READY"
        assert mock_alc.call_count == 0  # short-circuits after failure
        assert mock_sch.call_count == 0
        assert mock_s2.call_count == 0
        assert mock_perm.call_count == 0


def test_preflight_alembic_mismatch() -> None:
    os.environ["DATABASE_URL"] = MOCK_DATABASE_URL

    with (
        patch("scripts.db_preflight.check_env") as mock_env,
        patch("scripts.db_preflight.check_connectivity") as mock_conn,
        patch("scripts.db_preflight.check_alembic") as mock_alc,
    ):
        mock_env.return_value = {"database_url": MOCK_DATABASE_URL}
        mock_conn.return_value = {"engine_ok": True}
        mock_alc.side_effect = PreflightError("migration_mismatch", "current != head")

        result = run_preflight(quiet=True)
        assert result["status"] == "DB_NOT_READY"
        assert result["error_token"] == "migration_mismatch"


def test_preflight_missing_v3_schemas() -> None:
    os.environ["DATABASE_URL"] = MOCK_DATABASE_URL

    with (
        patch("scripts.db_preflight.check_env") as mock_env,
        patch("scripts.db_preflight.check_connectivity") as mock_conn,
        patch("scripts.db_preflight.check_alembic") as mock_alc,
        patch("scripts.db_preflight.check_schemas") as mock_sch,
    ):
        mock_env.return_value = {"database_url": MOCK_DATABASE_URL}
        mock_conn.return_value = {"engine_ok": True}
        mock_alc.return_value = {"current_revision": "004abc", "head_revision": "004abc", "match": True}
        mock_sch.side_effect = PreflightError("missing_schema", "strategy, governance missing")

        result = run_preflight(quiet=True)
        assert result["status"] == "DB_NOT_READY"
        assert result["error_token"] == "missing_schema"


def test_preflight_missing_system2_tables() -> None:
    os.environ["DATABASE_URL"] = MOCK_DATABASE_URL

    with (
        patch("scripts.db_preflight.check_env") as mock_env,
        patch("scripts.db_preflight.check_connectivity") as mock_conn,
        patch("scripts.db_preflight.check_alembic") as mock_alc,
        patch("scripts.db_preflight.check_schemas") as mock_sch,
        patch("scripts.db_preflight.check_system2_tables") as mock_s2,
    ):
        mock_env.return_value = {"database_url": MOCK_DATABASE_URL}
        mock_conn.return_value = {"engine_ok": True}
        mock_alc.return_value = {"current_revision": "004abc", "head_revision": "004abc", "match": True}
        mock_sch.return_value = {"existing_schemas": list(_ALL_REQUIRED_SCHEMAS), "all_present": True}
        mock_s2.side_effect = PreflightError("missing_table", "runtime, intent missing")

        result = run_preflight(quiet=True)
        assert result["status"] == "DB_NOT_READY"
        assert result["error_token"] == "missing_table"


def test_preflight_reports_ready_when_all_pass() -> None:
    os.environ["DATABASE_URL"] = MOCK_DATABASE_URL

    with (
        patch("scripts.db_preflight.check_env") as mock_env,
        patch("scripts.db_preflight.check_connectivity") as mock_conn,
        patch("scripts.db_preflight.check_alembic") as mock_alc,
        patch("scripts.db_preflight.check_schemas") as mock_sch,
        patch("scripts.db_preflight.check_system2_tables") as mock_s2,
        patch("scripts.db_preflight.check_permissions") as mock_perm,
        patch("scripts.db_preflight.check_system_resources") as mock_res,
    ):
        mock_env.return_value = {"database_url": MOCK_DATABASE_URL}
        mock_conn.return_value = {"engine_ok": True}
        mock_alc.return_value = {"current_revision": "004abc", "head_revision": "004abc", "match": True}
        mock_sch.return_value = {"existing_schemas": list(_ALL_REQUIRED_SCHEMAS), "all_present": True}
        mock_s2.return_value = {"existing_operations_tables": list(_SYSTEM2_OPERATIONS_TABLES), "all_present": True}
        mock_perm.return_value = {"current_user": "svos_app", "read_write_ok": True}
        mock_res.return_value = {"disk_ok": True, "ram_ok": True, "disk_free_gb": 15.0, "ram_available_gb": 4.0}

        result = run_preflight(quiet=True)
        assert result["status"] == "DB_READY"
        assert result["error_token"] is None
        # All 8 steps should be present
        assert len(result["steps"]) == 8


def test_preflight_cli_returns_zero_on_ready(monkeypatch) -> None:
    """CLI's --quiet/exit-code contract, with run_preflight mocked.

    In-process (not subprocess): a mock only patches the object in this
    process's memory, so a real subprocess re-importing scripts.db_preflight
    fresh would never see it and would always exercise the real (unready,
    no-DB) path regardless of the mock.
    """
    monkeypatch.setattr(sys, "argv", ["db_preflight.py", "--quiet"])
    with patch("scripts.db_preflight.run_preflight") as mock_run:
        mock_run.return_value = {"status": "DB_READY", "error_token": None, "steps": []}
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0


def test_preflight_cli_returns_one_on_not_ready() -> None:
    """End-to-end subprocess call without DATABASE_URL — should fail."""
    env = {k: v for k, v in os.environ.items() if k != "DATABASE_URL"}
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "db_preflight.py"), "--quiet"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )
    assert result.returncode == 1


# ═══════════════════════════════════════════════════════════════════════════════
# Safety: no live trading or broker write paths touched
# ═══════════════════════════════════════════════════════════════════════════════

def test_preflight_does_not_import_broker_modules() -> None:
    """Preflight must never import execution or broker modules."""
    source = (ROOT / "scripts" / "db_preflight.py").read_text(encoding="utf-8")
    dangerous = [
        "metaapi",
        "MT5Connector",
        "VantageDemoExecutor",
        "LIVE_TRADING",
        "live_trading",
        "confirm_token",
        "CONFIRM",
    ]
    for term in dangerous:
        assert term not in source, f"Preflight must not reference broker/deployment terms: {term}"


def test_preflight_does_not_import_dashboard_or_lifecycle() -> None:
    """Preflight must be self-contained — no dashboard, no lifecycle mutation."""
    source = (ROOT / "scripts" / "db_preflight.py").read_text(encoding="utf-8")
    forbidden = [
        "svos.lifecycle",
        "svos.orchestration",
        "svos.governance",
        "dashboard",
        "strategy_service",
        "pipeline_service",
    ]
    for term in forbidden:
        assert term not in source, f"Preflight must not import {term}"
