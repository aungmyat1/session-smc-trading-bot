"""
Demo Validation Mode — session tracking.

A validation session is a longer-lived campaign (spans one or more runner
restarts) distinct from operations.runtime's one-row-per-process-start
record. It answers "which build, whose account, which config was this batch
of demo trades run under" for the eventual promotion decision.

Design mirrors execution/risk_portfolio_store.py: module-level SessionLocal,
best-effort writes (never raise, log and swallow), reads default to None on
any failure. No new persistence pattern introduced.

Public API:
    mgr = ValidationSessionManager()
    session_id = mgr.start(operator=..., broker=..., account=...)
    mgr.resume(session_id) -> dict | None   # survives a runner restart
    mgr.end(session_id, status="completed")
    mgr.active_session() -> dict | None     # most recent session with no ended_at
"""

from __future__ import annotations

import hashlib
import logging
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from db.connection import SessionLocal
from db.models import ValidationSession

_log = logging.getLogger("execution.validation_session")

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _git_commit() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()[:64]
    except Exception as exc:
        _log.debug("git commit lookup skipped: %s", exc)
    return "unknown"


def _software_version() -> str:
    pyproject = _REPO_ROOT / "pyproject.toml"
    try:
        for line in pyproject.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("version"):
                return stripped.split("=", 1)[1].strip().strip('"')
    except Exception as exc:
        _log.debug("version lookup skipped: %s", exc)
    return "unknown"


def config_hash(config_path: str | Path) -> str:
    """SHA-256 of a config file's bytes — lets a report say exactly which
    config a session ran under, independent of the filename/path."""
    try:
        data = Path(config_path).read_bytes()
        return hashlib.sha256(data).hexdigest()[:64]
    except Exception as exc:
        _log.debug("config hash skipped: %s", exc)
        return "unknown"


class ValidationSessionManager:
    """Durable Postgres-backed validation session tracker.

    Falls back to a no-op (returns a locally-generated session_id, but state
    is not durable) when the DB is unavailable, matching the best-effort
    contract of the rest of the operations.* recorders — a validation
    session is an audit/reporting construct, not a safety gate.
    """

    def start(
        self,
        *,
        operator: str,
        broker: str,
        account: str,
        config_path: str | Path | None = None,
    ) -> str:
        session_id = f"val-{uuid4().hex[:12]}"
        if SessionLocal is None:
            _log.warning("validation session %s not persisted: DATABASE_URL not configured", session_id)
            return session_id
        session = SessionLocal()
        try:
            session.add(ValidationSession(
                session_id=session_id,
                operator=operator,
                broker=broker,
                account=account,
                software_version=_software_version(),
                git_commit=_git_commit(),
                config_hash=config_hash(config_path) if config_path else "unknown",
                status="active",
                started_at=datetime.now(timezone.utc),
            ))
            session.commit()
        except Exception as exc:
            session.rollback()
            _log.warning("validation session start not persisted (%s): %s", session_id, exc)
        finally:
            session.close()
        return session_id

    def resume(self, session_id: str) -> dict[str, Any] | None:
        if SessionLocal is None:
            return None
        session = SessionLocal()
        try:
            row = session.query(ValidationSession).filter_by(session_id=session_id).first()
            return _row_to_dict(row) if row is not None else None
        except Exception as exc:
            _log.warning("validation session resume skipped (%s): %s", session_id, exc)
            return None
        finally:
            session.close()

    def active_session(self) -> dict[str, Any] | None:
        if SessionLocal is None:
            return None
        session = SessionLocal()
        try:
            row = (
                session.query(ValidationSession)
                .filter_by(status="active")
                .order_by(ValidationSession.started_at.desc())
                .first()
            )
            return _row_to_dict(row) if row is not None else None
        except Exception as exc:
            _log.warning("validation active_session lookup skipped: %s", exc)
            return None
        finally:
            session.close()

    def end(self, session_id: str, status: str = "completed") -> None:
        if SessionLocal is None:
            return
        session = SessionLocal()
        try:
            row = session.query(ValidationSession).filter_by(session_id=session_id).first()
            if row is not None:
                row.status = status
                row.ended_at = datetime.now(timezone.utc)
                session.commit()
        except Exception as exc:
            session.rollback()
            _log.warning("validation session end not persisted (%s): %s", session_id, exc)
        finally:
            session.close()


def _row_to_dict(row: ValidationSession) -> dict[str, Any]:
    return {
        "session_id": row.session_id,
        "operator": row.operator,
        "broker": row.broker,
        "account": row.account,
        "software_version": row.software_version,
        "git_commit": row.git_commit,
        "config_hash": row.config_hash,
        "status": row.status,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "ended_at": row.ended_at.isoformat() if row.ended_at else None,
    }
