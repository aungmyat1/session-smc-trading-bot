"""Transactional operational persistence and emergency audit sink."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol

from sqlalchemy import text

from shared.serialization import now_iso


class OperationsUnavailable(RuntimeError):
    pass


class OperationsRepository(Protocol):
    def append_event(self, event_type: str, payload: Mapping[str, Any]) -> str: ...
    def checkpoint(self, runtime_id: str, state: Mapping[str, Any]) -> None: ...
    def latest_checkpoint(self, runtime_id: str) -> Mapping[str, Any] | None: ...
    def list_records(self, record_type: str, *, limit: int = 100) -> list[Mapping[str, Any]]: ...


@dataclass(slots=True)
class PostgresOperationsRepository:
    """PostgreSQL is authoritative; errors never fall back to JSONL mutation."""

    session: Any

    def append_event(self, event_type: str, payload: Mapping[str, Any]) -> str:
        try:
            row = self.session.execute(
                text("INSERT INTO operations.execution_event(event_type,payload,created_at) VALUES (:t,CAST(:p AS jsonb),now()) RETURNING id"),
                {"t": event_type, "p": json.dumps(dict(payload), sort_keys=True)},
            ).scalar_one()
            self.session.commit()
            return str(row)
        except Exception as exc:
            self.session.rollback()
            raise OperationsUnavailable("operations database mutation failed") from exc

    def checkpoint(self, runtime_id: str, state: Mapping[str, Any]) -> None:
        try:
            self.session.execute(
                text("INSERT INTO operations.recovery_checkpoint(runtime_id,state,created_at) VALUES (:r,CAST(:s AS jsonb),now())"),
                {"r": runtime_id, "s": json.dumps(dict(state), sort_keys=True)},
            )
            self.session.commit()
        except Exception as exc:
            self.session.rollback()
            raise OperationsUnavailable("checkpoint persistence failed") from exc

    def latest_checkpoint(self, runtime_id: str) -> Mapping[str, Any] | None:
        try:
            row = self.session.execute(text("SELECT state FROM operations.recovery_checkpoint WHERE runtime_id=:r ORDER BY created_at DESC LIMIT 1"), {"r": runtime_id}).scalar_one_or_none()
            return row
        except Exception as exc:
            raise OperationsUnavailable("checkpoint read failed") from exc

    def list_records(self, record_type: str, *, limit: int = 100) -> list[Mapping[str, Any]]:
        queries = {
            "execution_event": "SELECT * FROM operations.execution_event ORDER BY created_at DESC LIMIT :n",
            "runtime": "SELECT * FROM operations.runtime ORDER BY created_at DESC LIMIT :n",
            "market_data_health": "SELECT * FROM operations.market_data_health ORDER BY created_at DESC LIMIT :n",
            "intent": "SELECT * FROM operations.intent ORDER BY created_at DESC LIMIT :n",
            "risk_decision": "SELECT * FROM operations.risk_decision ORDER BY created_at DESC LIMIT :n",
            "order_record": "SELECT * FROM operations.order_record ORDER BY created_at DESC LIMIT :n",
            "fill": "SELECT * FROM operations.fill ORDER BY created_at DESC LIMIT :n",
            "position_record": "SELECT * FROM operations.position_record ORDER BY created_at DESC LIMIT :n",
            "reconciliation": "SELECT * FROM operations.reconciliation ORDER BY created_at DESC LIMIT :n",
            "incident": "SELECT * FROM operations.incident ORDER BY opened_at DESC LIMIT :n",
            "recovery_checkpoint": "SELECT * FROM operations.recovery_checkpoint ORDER BY created_at DESC LIMIT :n",
        }
        query = queries.get(record_type)
        if query is None:
            raise ValueError("unsupported operations record type")
        try:
            rows = self.session.execute(text(query), {"n": min(max(limit, 1), 1000)}).mappings()
            return [dict(row) for row in rows]
        except Exception as exc:
            raise OperationsUnavailable("operations query failed") from exc


class EmergencyAuditSink:
    """Append-only diagnostics. It is never read as operational authority."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def append(self, event_type: str, payload: Mapping[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        record = {"event_type": event_type, "created_at": now_iso(), "payload": dict(payload), "authoritative": False}
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
