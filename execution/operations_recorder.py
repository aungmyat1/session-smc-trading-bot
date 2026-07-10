"""
Durable, best-effort recording into the Postgres operations.* schema
(migration 004, `db/models.py`) — SYSTEM2_MASTER_PLAN.md Phase 2, Sprint 2.3.

Reuses the CanonicalExecutionPipeline event stream already wired in Sprint 2.1
(scripts/run_st_a2_demo.py) instead of adding a second, parallel persistence
design: every NormalizedExecutionEvent is logged to operations.execution_event,
and intent/risk_decision/order_record get their own typed row. Recovery passes
write one operations.recovery_checkpoint row.

Best-effort by design: a DB hiccup here must never block or crash the demo
trading loop (this is an audit/observability layer, not a safety gate — the
actual idempotency/no-duplicate-order guarantee already lives in
ExecutionStateStore, unchanged). Every write is wrapped and logged, never raised.

Public API:
    OperationsRecorder(runtime_id).record_runtime_start(status="running")
    OperationsRecorder(runtime_id).event_sink(normalized_event)
    OperationsRecorder(runtime_id).record_recovery_checkpoint(resolved, orphaned)
    get_recent_events(limit=50) -> list[dict]  # read side, for the dashboard backend
    get_recent_runtimes(limit=10) -> list[dict]
    db_health_check() -> dict  # read side, for the System 2 readiness aggregator
"""

from __future__ import annotations

import logging
import time
from typing import Any

from sqlalchemy import text

from db.connection import SessionLocal
from db.models import (
    ExecutionEvent, Fill, Intent, OrderRecord, PositionRecord, Reconciliation,
    RecoveryCheckpoint, RiskDecision, Runtime,
)

_log = logging.getLogger("execution.operations_recorder")


def _read(fn, default: Any) -> Any:
    """Best-effort read, mirroring the writer's never-raise contract — a DB
    hiccup must degrade a dashboard widget to empty, not break the request."""
    if SessionLocal is None:
        return default
    session = SessionLocal()
    try:
        return fn(session)
    except Exception as exc:
        _log.warning("operations recorder read skipped: %s", exc)
        return default
    finally:
        session.close()


# Telegram alert categories (monitoring/telegram.py's alert_category values)
# that indicate a real operational problem, not routine informational traffic
# — used so persisted telegram_alert:* events aren't all flatly "info".
_TELEGRAM_WARNING_CATEGORIES = frozenset({"circuit_breaker", "reconciliation_mismatch"})
_TELEGRAM_ERROR_CATEGORIES = frozenset({"error", "emergency_stop", "watchdog_critical", "reconnect_failure"})


def _classify_event_severity(event_type: str) -> str:
    lowered = event_type.lower()
    if lowered.startswith("telegram_alert:"):
        category = lowered.split(":", 1)[1]
        if category in _TELEGRAM_ERROR_CATEGORIES:
            return "error"
        if category in _TELEGRAM_WARNING_CATEGORIES:
            return "warning"
        return "info"
    return "error" if "reject" in lowered else "info"


def get_recent_events(limit: int = 50) -> list[dict[str, Any]]:
    """Merged, newest-first view of operations.execution_event and
    operations.recovery_checkpoint — the durable event/alert history the
    dashboard's "Operational Events" capability reads from."""

    def _query(session) -> list[dict[str, Any]]:
        events = (
            session.query(ExecutionEvent).order_by(ExecutionEvent.created_at.desc()).limit(limit).all()
        )
        checkpoints = (
            session.query(RecoveryCheckpoint).order_by(RecoveryCheckpoint.created_at.desc()).limit(limit).all()
        )
        merged = [
            {
                "type": "execution_event",
                "event_type": e.event_type,
                "severity": _classify_event_severity(e.event_type),
                "payload": e.payload,
                "created_at": e.created_at.isoformat(),
            }
            for e in events
        ] + [
            {
                "type": "recovery_checkpoint",
                "runtime_id": c.runtime_id,
                "severity": "warning" if (c.state or {}).get("resolved") else "info",
                "state": c.state,
                "created_at": c.created_at.isoformat(),
            }
            for c in checkpoints
        ]
        merged.sort(key=lambda r: r["created_at"], reverse=True)
        return merged[:limit]

    return _read(_query, [])


def get_recent_runtimes(limit: int = 10) -> list[dict[str, Any]]:
    """Recent runtime-start records — startup/restart history for the
    Operational Events capability's "startup events" field."""

    def _query(session) -> list[dict[str, Any]]:
        rows = session.query(Runtime).order_by(Runtime.created_at.desc()).limit(limit).all()
        return [
            {"runtime_id": r.runtime_id, "status": r.status, "payload": r.payload, "created_at": r.created_at.isoformat()}
            for r in rows
        ]

    return _read(_query, [])


def db_health_check() -> dict[str, Any]:
    """Direct Postgres reachability probe for the System 2 readiness aggregator.

    Distinct from _read()'s best-effort default-on-any-failure contract: a
    fail-closed readiness check needs to know *why* the database is
    unreachable (not configured vs. configured-but-down), not just silently
    degrade to an empty default like the dashboard-widget reads above do."""
    if SessionLocal is None:
        return {"reachable": False, "configured": False, "latency_ms": None, "error": "DATABASE_URL not configured"}
    started = time.monotonic()
    session = SessionLocal()
    try:
        session.execute(text("SELECT 1"))
        return {"reachable": True, "configured": True, "latency_ms": round((time.monotonic() - started) * 1000, 1), "error": None}
    except Exception as exc:
        _log.warning("db_health_check failed: %s", exc)
        return {"reachable": False, "configured": True, "latency_ms": None, "error": str(exc)}
    finally:
        session.close()


def record_telegram_alert(category: str, message: str, *, sent: bool) -> None:
    """Best-effort persistence of every Telegram alert attempt into the same
    operations.execution_event table other execution events already use —
    SYSTEM2_MASTER_PLAN.md Phase 3 (2026-07-06). No second event store.

    `sent=False` marks an alert that was rate-limited/suppressed by
    TelegramAlerter's own cooldown rather than actually delivered — both are
    recorded, since the underlying condition still happened even if the
    Telegram message itself was throttled; historical visibility shouldn't
    silently drop those. Never raises — a DB hiccup must not block sending
    the real Telegram message, matching this module's other write paths."""
    if SessionLocal is None:
        return
    session = SessionLocal()
    try:
        session.add(ExecutionEvent(event_type=f"telegram_alert:{category}", payload={"message": message, "sent": sent}))
        session.commit()
    except Exception as exc:
        session.rollback()
        _log.warning("telegram alert persistence skipped: %s", exc)
    finally:
        session.close()


def record_fill(order_id: str, status: str, payload: dict[str, Any]) -> None:
    """Best-effort write to operations.fill — populates a table defined by
    migration 004 but never written to; Demo Validation Mode's lifecycle
    recorder is the first caller (execution/validation_recorder.py)."""
    if SessionLocal is None:
        return
    session = SessionLocal()
    try:
        session.add(Fill(order_id=order_id, status=status, payload=payload))
        session.commit()
    except Exception as exc:
        session.rollback()
        _log.warning("fill record skipped (%s): %s", order_id, exc)
    finally:
        session.close()


def record_position(symbol: str, status: str, payload: dict[str, Any]) -> None:
    """Best-effort write to operations.position_record (see record_fill)."""
    if SessionLocal is None:
        return
    session = SessionLocal()
    try:
        session.add(PositionRecord(symbol=symbol, status=status, payload=payload))
        session.commit()
    except Exception as exc:
        session.rollback()
        _log.warning("position record skipped (%s): %s", symbol, exc)
    finally:
        session.close()


def record_reconciliation(runtime_id: str, consistent: bool, payload: dict[str, Any]) -> None:
    """Best-effort write to operations.reconciliation (see record_fill)."""
    if SessionLocal is None:
        return
    session = SessionLocal()
    try:
        session.add(Reconciliation(runtime_id=runtime_id, consistent=consistent, payload=payload))
        session.commit()
    except Exception as exc:
        session.rollback()
        _log.warning("reconciliation record skipped (%s): %s", runtime_id, exc)
    finally:
        session.close()


class OperationsRecorder:
    def __init__(self, runtime_id: str) -> None:
        self.runtime_id = runtime_id

    def _run(self, fn) -> None:
        if SessionLocal is None:
            return
        session = SessionLocal()
        try:
            fn(session)
            session.commit()
        except Exception as exc:
            session.rollback()
            _log.warning("operations recorder write skipped: %s", exc)
        finally:
            session.close()

    def record_runtime_start(self, status: str = "running", **payload: Any) -> None:
        self._run(lambda s: s.add(Runtime(runtime_id=self.runtime_id, status=status, payload=payload)))

    def event_sink(self, event: Any) -> None:
        """Pass directly as CanonicalExecutionPipeline(event_sink=...)."""
        record = event.to_dict()

        def _write(session):
            session.add(ExecutionEvent(event_type=record["event_type"], payload=record))
            if record["event_type"] == "intent_received" and record.get("intent_id"):
                session.add(Intent(intent_id=record["intent_id"], symbol=record.get("symbol", ""), payload=record))
            elif record["event_type"] == "risk_decision":
                session.add(RiskDecision(
                    intent_id=record.get("intent_id", ""),
                    approved=bool(record.get("approved")),
                    payload=record,
                ))
            elif record["event_type"] == "execution_result":
                session.add(OrderRecord(
                    order_id=record.get("reference", ""),
                    idempotency_key=record.get("intent_id", "") or record["event_id"],
                    status=record.get("status", ""),
                    payload=record,
                ))

        self._run(_write)

    def record_recovery_checkpoint(self, resolved: list, orphaned: list) -> None:
        state = {
            "resolved": [
                {
                    "execution_id": r.execution_id, "final_state": r.final_state,
                    "broker_order_id": r.broker_order_id, "note": r.note,
                }
                for r in resolved
            ],
            "orphaned_positions": orphaned,
        }
        self._run(lambda s: s.add(RecoveryCheckpoint(runtime_id=self.runtime_id, state=state, payload={})))
