#!/usr/bin/env python3
"""
Database Preflight Verification — scripts/db_preflight.py

Checks PostgreSQL migration readiness and schema completeness.

Output (machine-readable exit codes):
    0 = DB_READY       — all checks pass
    1 = DB_NOT_READY   — at least one check failed

Error tokens (written to stderr on failure):
    missing_env
    connection_failed
    migration_mismatch
    missing_schema
    missing_table
    permission_error

Usage:
    python scripts/db_preflight.py
    python scripts/db_preflight.py --json
    DB_READY=$(python scripts/db_preflight.py --quiet && echo "ok" || echo "fail")
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text

_ROOT = Path(__file__).resolve().parent.parent

# ── Required v2 schemas (legacy) ──────────────────────────────────────────────
_REQUIRED_V2_SCHEMAS = frozenset({"market", "research", "analytics"})

# ── Required v3 schemas (control plane) ───────────────────────────────────────
_REQUIRED_V3_SCHEMAS = frozenset(
    {"strategy", "governance", "evidence", "experiments", "robustness", "execution", "operations"}
)

# ── Required System 2 operation tables (migration 004) ────────────────────────
_SYSTEM2_OPERATIONS_TABLES = frozenset(
    {
        "runtime",
        "market_data_health",
        "intent",
        "risk_decision",
        "order_record",
        "fill",
        "position_record",
        "reconciliation",
        "recovery_checkpoint",
        "execution_event",
    }
)

# ── All required schemas ─────────────────────────────────────────────────────
_ALL_REQUIRED_SCHEMAS = _REQUIRED_V2_SCHEMAS | _REQUIRED_V3_SCHEMAS


class PreflightError(Exception):
    """Raised when a preflight check fails with a known error token."""

    def __init__(self, token: str, message: str) -> None:
        self.token = token
        self.message = message
        super().__init__(f"[{token}] {message}")


# ── Checks ────────────────────────────────────────────────────────────────────


def _load_env() -> None:
    try:
        from dotenv import load_dotenv
        load_dotenv(_ROOT / ".env")
    except ImportError:
        pass


def _normalize_url(url: str) -> str:
    for prefix in ("postgresql+asyncpg://", "postgresql+psycopg2://"):
        if url.startswith(prefix):
            return url.replace(prefix, "postgresql://", 1)
    return url


def check_env() -> dict[str, Any]:
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise PreflightError("missing_env", "DATABASE_URL is not set or is empty")
    if not isinstance(url, str) or len(url) < 20:
        raise PreflightError("missing_env", "DATABASE_URL looks truncated or invalid")
    return {"database_url": _normalize_url(url), "raw_url_prefix": url[:15] + "..."}


def check_alembic() -> dict[str, Any]:
    current_revision: str | None = None
    head_revision: str | None = None

    try:
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "current"],
            cwd=_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
        current_out = (result.stdout or "").strip()
        # alembic current outputs something like "004 (head)" or "004" — this
        # project uses short numeric revision ids (see db/migrations/versions),
        # not the 12-char hex hashes alembic generates by default, so any
        # non-empty first token is a valid revision id.
        if current_out and "No current revision" not in current_out:
            parts = current_out.split()
            if parts:
                candidate = parts[0].strip()
                if candidate:
                    current_revision = candidate
    except Exception as exc:
        raise PreflightError("migration_mismatch", f"Cannot check alembic current revision: {exc}")

    try:
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "heads"],
            cwd=_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
        head_out = (result.stdout or "").strip()
        if head_out:
            # Multiple heads are separated by newlines
            first_line = head_out.splitlines()[0].strip()
            if first_line:
                parts = first_line.split()
                if parts:
                    candidate = parts[0].strip()
                    if candidate:
                        head_revision = candidate
    except Exception as exc:
        raise PreflightError("migration_mismatch", f"Cannot check alembic head revision: {exc}")

    if head_revision is None:
        raise PreflightError("migration_mismatch", "No alembic head revision found — no migrations defined?")

    if current_revision != head_revision:
        raise PreflightError(
            "migration_mismatch",
            f"Database is at revision {current_revision} but head is {head_revision}. "
            f"Run: alembic upgrade head",
        )

    return {
        "current_revision": current_revision,
        "head_revision": head_revision,
        "match": True,
    }


def check_connectivity(database_url: str) -> dict[str, Any]:
    try:
        engine = create_engine(database_url, pool_pre_ping=True, connect_args={"connect_timeout": 5})
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1 AS ok"))
            row = result.fetchone()
            if not row or row[0] != 1:
                raise PreflightError("connection_failed", "SELECT 1 returned unexpected result")
    except PreflightError:
        raise
    except Exception as exc:
        raise PreflightError("connection_failed", f"Cannot connect to PostgreSQL: {exc}")

    return {"engine_ok": True}


def check_schemas(database_url: str) -> dict[str, Any]:
    engine = create_engine(database_url, pool_pre_ping=True, connect_args={"connect_timeout": 5})

    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT schema_name FROM information_schema.schemata WHERE schema_name NOT IN ('information_schema', 'pg_catalog', 'pg_toast')")
        )
        existing = {row[0] for row in result.fetchall()}

    missing = _ALL_REQUIRED_SCHEMAS - existing
    if missing:
        raise PreflightError(
            "missing_schema",
            f"Required schemas missing: {', '.join(sorted(missing))}. "
            f"Run: alembic upgrade head",
        )

    return {"existing_schemas": sorted(existing), "all_present": True}


def check_system2_tables(database_url: str) -> dict[str, Any]:
    engine = create_engine(database_url, pool_pre_ping=True, connect_args={"connect_timeout": 5})

    with engine.connect() as conn:
        result = conn.execute(
            text(
                "SELECT table_schema, table_name "
                "FROM information_schema.tables "
                "WHERE table_schema = 'operations' "
                "AND table_type = 'BASE TABLE'"
            )
        )
        existing_tables = {row[1] for row in result.fetchall()}

    missing = _SYSTEM2_OPERATIONS_TABLES - existing_tables
    if missing:
        raise PreflightError(
            "missing_table",
            f"System 2 operations tables missing: {', '.join(sorted(missing))}. "
            f"Run: alembic upgrade head",
        )

    return {"existing_operations_tables": sorted(existing_tables), "all_present": True}


def check_permissions(database_url: str) -> dict[str, Any]:
    engine = create_engine(database_url, pool_pre_ping=True, connect_args={"connect_timeout": 5})

    with engine.connect() as conn:
        # Check current user
        user_row = conn.execute(text("SELECT current_user")).fetchone()
        current_user = user_row[0] if user_row else "unknown"

        # Check read permission: can query a known table
        conn.execute(text("SELECT COUNT(*) FROM operations.runtime")).fetchone()

        # Check write permission: insert then roll back so nothing persists.
        # conn already autobegan a transaction via the reads above, so calling
        # conn.begin() here would conflict with it (InvalidRequestError).
        conn.execute(
            text(
                "INSERT INTO operations.intent (intent_id, symbol, payload) "
                "VALUES ('__db_preflight_check__', '__PREFLIGHT__', "
                "'{\"preflight_check\": true, \"created_by\": \"db_preflight.py\"}') "
                "ON CONFLICT DO NOTHING"
            )
        )
        conn.rollback()

    return {"current_user": current_user, "read_write_ok": True}


def check_system_resources() -> dict[str, Any]:
    """Check disk and RAM if available — warn only, never block."""
    result: dict[str, Any] = {"disk_ok": True, "ram_ok": True}

    # Disk check
    try:
        stat = os.statvfs(str(_ROOT))
        free_bytes = stat.f_frsize * stat.f_bavail
        free_gb = free_bytes / (1024 ** 3)
        result["disk_free_gb"] = round(free_gb, 1)
        if free_gb < 1.0:
            result["disk_ok"] = False
            result["disk_warning"] = f"Very low disk space: {free_gb:.1f} GB free"
        elif free_gb < 5.0:
            result["disk_warning"] = f"Low disk space: {free_gb:.1f} GB free"
    except Exception:
        result["disk_ok"] = True
        result["disk_skip"] = "Cannot check disk space"

    # RAM check
    try:
        with open("/proc/meminfo", "r") as fh:
            for line in fh:
                if line.startswith("MemAvailable:"):
                    parts = line.split()
                    avail_kb = int(parts[1]) if len(parts) >= 2 else 0
                    avail_gb = avail_kb / (1024 ** 2)
                    result["ram_available_gb"] = round(avail_gb, 1)
                    if avail_gb < 0.5:
                        result["ram_ok"] = False
                        result["ram_warning"] = f"Very low available RAM: {avail_gb:.1f} GB"
                    elif avail_gb < 2.0:
                        result["ram_warning"] = f"Low available RAM: {avail_gb:.1f} GB"
                    break
    except Exception:
        result["ram_ok"] = True
        result["ram_skip"] = "Cannot check available RAM"

    return result


# ── Runner ─────────────────────────────────────────────────────────────────────


def run_preflight(quiet: bool = False) -> dict[str, Any]:
    """Execute all preflight checks and return a result dict."""
    _load_env()

    steps: list[dict[str, Any]] = []
    status = "DB_READY"
    error_token: str | None = None
    error_message: str | None = None

    # Step 1: Environment
    try:
        env_result = check_env()
        url = env_result["database_url"]
        steps.append({"check": "DATABASE_URL", "status": "PASS", "detail": url[:25] + "..."})
    except PreflightError as exc:
        steps.append({"check": "DATABASE_URL", "status": "FAIL", "detail": exc.message})
        status = "DB_NOT_READY"
        if error_token is None:
            error_token = exc.token
            error_message = exc.message
        if not quiet:
            print(f"[{exc.token}] {exc.message}", file=sys.stderr)
        return {"status": status, "error_token": error_token, "error_message": error_message, "steps": steps}

    # Step 2: Connectivity
    try:
        conn_result = check_connectivity(url)
        steps.append({"check": "connectivity", "status": "PASS", "detail": "SQLAlchemy engine connects successfully"})
    except PreflightError as exc:
        steps.append({"check": "connectivity", "status": "FAIL", "detail": exc.message})
        status = "DB_NOT_READY"
        if error_token is None:
            error_token = exc.token
            error_message = exc.message
        if not quiet:
            print(f"[{exc.token}] {exc.message}", file=sys.stderr)
        return {"status": status, "error_token": error_token, "error_message": error_message, "steps": steps}

    # Step 3: Alembic installed
    alembic_installed = False
    try:
        import alembic  # noqa: F401
        alembic_installed = True
        steps.append({"check": "alembic_installed", "status": "PASS", "detail": "alembic package is importable"})
    except ImportError:
        steps.append({"check": "alembic_installed", "status": "FAIL", "detail": "alembic package is not installed"})
        status = "DB_NOT_READY"
        if error_token is None:
            error_token = "missing_env"
            error_message = "alembic is not installed"
        if not quiet:
            print("[missing_env] alembic is not installed", file=sys.stderr)
        return {"status": status, "error_token": error_token, "error_message": error_message, "steps": steps}

    # Step 4: Alembic revisions
    if alembic_installed:
        try:
            alembic_result = check_alembic()
            steps.append(
                {
                    "check": "alembic_revisions",
                    "status": "PASS",
                    "detail": f"current={alembic_result['current_revision']} head={alembic_result['head_revision']}",
                }
            )
        except PreflightError as exc:
            steps.append({"check": "alembic_revisions", "status": "FAIL", "detail": exc.message})
            status = "DB_NOT_READY"
            if error_token is None:
                error_token = exc.token
                error_message = exc.message
            if not quiet:
                print(f"[{exc.token}] {exc.message}", file=sys.stderr)
            # Fail fast: schema/table checks against a database at the wrong
            # migration revision would be meaningless (or misleading).
            return {"status": status, "error_token": error_token, "error_message": error_message, "steps": steps}

    # Step 5: Schemas
    try:
        schema_result = check_schemas(url)
        steps.append({"check": "required_schemas", "status": "PASS", "detail": f"found {len(schema_result['existing_schemas'])} schemas"})
    except PreflightError as exc:
        steps.append({"check": "required_schemas", "status": "FAIL", "detail": exc.message})
        status = "DB_NOT_READY"
        if error_token is None:
            error_token = exc.token
            error_message = exc.message
        if not quiet:
            print(f"[{exc.token}] {exc.message}", file=sys.stderr)
        return {"status": status, "error_token": error_token, "error_message": error_message, "steps": steps}

    # Step 6: System 2 tables
    try:
        s2_result = check_system2_tables(url)
        steps.append({"check": "system2_tables", "status": "PASS", "detail": f"found {len(s2_result['existing_operations_tables'])} operations tables"})
    except PreflightError as exc:
        steps.append({"check": "system2_tables", "status": "FAIL", "detail": exc.message})
        status = "DB_NOT_READY"
        if error_token is None:
            error_token = exc.token
            error_message = exc.message
        if not quiet:
            print(f"[{exc.token}] {exc.message}", file=sys.stderr)
        return {"status": status, "error_token": error_token, "error_message": error_message, "steps": steps}

    # Step 7: Permissions
    try:
        perm_result = check_permissions(url)
        steps.append({"check": "permissions", "status": "PASS", "detail": f"user={perm_result['current_user']} read/write ok"})
    except PreflightError as exc:
        steps.append({"check": "permissions", "status": "FAIL", "detail": exc.message})
        status = "DB_NOT_READY"
        if error_token is None:
            error_token = exc.token
            error_message = exc.message
        if not quiet:
            print(f"[{exc.token}] {exc.message}", file=sys.stderr)
        return {"status": status, "error_token": error_token, "error_message": error_message, "steps": steps}

    # Step 8: System resources (warn only)
    resource_result = check_system_resources()
    steps.append(
        {
            "check": "system_resources",
            "status": "PASS" if resource_result.get("disk_ok") and resource_result.get("ram_ok") else "WARN",
            "detail": (
                f"disk_free={resource_result.get('disk_free_gb', '?')}GB "
                f"ram_available={resource_result.get('ram_available_gb', '?')}GB"
            ),
            "warnings": [resource_result.get(k) for k in ("disk_warning", "ram_warning") if resource_result.get(k)],
        }
    )

    if not quiet and status == "DB_READY":
        print("DB_READY")
    return {"status": status, "error_token": error_token, "error_message": error_message, "steps": steps}


# ── CLI ────────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="Database preflight verification for the SVOS platform.")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON to stdout")
    parser.add_argument("--quiet", action="store_true", help="Suppress human-readable output; exit code only")
    args = parser.parse_args()

    result = run_preflight(quiet=args.quiet)

    if args.json:
        print(json.dumps(result, indent=2, default=str))
    elif not args.quiet:
        steps = result.get("steps", [])
        print()
        print("═" * 60)
        print("  Database Preflight Verification Report")
        print("═" * 60)
        print()
        for step in steps:
            icon = {"PASS": "✓", "WARN": "~", "FAIL": "✗"}.get(step["status"], "?")
            print(f"  {icon} {step['check']:<25} {step['status']:<5}  {step['detail']}")
            for warning in step.get("warnings", []):
                print(f"     ~ {warning}")
        print()
        print(f"  Result: {result['status']}")
        if result.get("error_token"):
            print(f"  Token:  {result['error_token']}")
        print("═" * 60)

    sys.exit(0 if result["status"] == "DB_READY" else 1)


if __name__ == "__main__":
    main()
