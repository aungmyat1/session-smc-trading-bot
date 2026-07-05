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
"""

from __future__ import annotations

import logging
from typing import Any

from db.connection import SessionLocal
from db.models import ExecutionEvent, Intent, OrderRecord, RecoveryCheckpoint, RiskDecision, Runtime

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
                "severity": "error" if "reject" in e.event_type.lower() else "info",
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
