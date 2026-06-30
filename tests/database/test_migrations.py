from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _offline_sql(database_url: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "DATABASE_URL": database_url}
    return subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head", "--sql"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_offline_upgrade_contains_baseline_and_control_plane() -> None:
    result = _offline_sql("postgresql://user:password@localhost/svos")
    assert result.returncode == 0, result.stderr
    assert "CREATE TABLE IF NOT EXISTS market.candles" in result.stdout
    assert "CREATE TABLE strategy.strategy" in result.stdout
    assert "CREATE TABLE governance.stage_state" in result.stdout


def test_database_url_with_percent_encoding_is_configparser_safe() -> None:
    result = _offline_sql("postgresql://user:p%21ss@localhost/svos")
    assert result.returncode == 0
    assert "p%21ss" not in result.stderr


def test_v3_does_not_recreate_v2_tables() -> None:
    migration = (ROOT / "db/migrations/versions/002_add_control_plane_v3.py").read_text(
        encoding="utf-8"
    )
    assert 'op.create_table(\n        "candles"' not in migration
    assert 'op.create_table(\n        "optimization_results"' not in migration
