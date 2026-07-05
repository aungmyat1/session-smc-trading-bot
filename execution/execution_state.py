from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


TERMINAL_STATES = {"COMPLETED", "FAILED_TERMINAL", "CANCELLED", "REJECTED"}

_ALLOWED_TRANSITIONS = {
    "SIGNAL_RECEIVED": {"GOVERNANCE_VALIDATED", "PERMISSION_VALIDATED", "RISK_APPROVED", "FAILED_TERMINAL"},
    "GOVERNANCE_VALIDATED": {"PERMISSION_VALIDATED", "FAILED_TERMINAL"},
    "PERMISSION_VALIDATED": {"RISK_APPROVED", "FAILED_TERMINAL"},
    "RISK_APPROVED": {"SUBMISSION_PENDING", "FAILED_TERMINAL"},
    "SUBMISSION_PENDING": {"BROKER_ACKNOWLEDGED", "RECOVERY_PENDING", "FAILED_TERMINAL", "REJECTED"},
    "BROKER_ACKNOWLEDGED": {"PARTIALLY_FILLED", "FILLED", "JOURNALED", "RECONCILED", "FAILED_TERMINAL"},
    "PARTIALLY_FILLED": {"FILLED", "CANCELLED", "RECOVERY_PENDING"},
    "FILLED": {"RECONCILED", "JOURNALED", "PROJECTED", "COMPLETED"},
    "REJECTED": set(),
    "CANCELLED": set(),
    "RECOVERY_PENDING": {"RECONCILED", "BROKER_ACKNOWLEDGED", "FAILED_TERMINAL"},
    "RECONCILED": {"JOURNALED", "PROJECTED", "COMPLETED"},
    "JOURNALED": {"PROJECTED", "COMPLETED"},
    "PROJECTED": {"COMPLETED"},
    "COMPLETED": set(),
    "FAILED_TERMINAL": set(),
}


def _shortest_path(start: str, goal: str) -> list[str] | None:
    """BFS over `_ALLOWED_TRANSITIONS` for the shortest legal state sequence
    from `start` to `goal` (inclusive of both ends), or None if unreachable."""
    if start == goal:
        return [start]
    from collections import deque

    frontier: deque[list[str]] = deque([[start]])
    seen = {start}
    while frontier:
        path = frontier.popleft()
        for nxt in _ALLOWED_TRANSITIONS.get(path[-1], ()):
            if nxt in seen:
                continue
            new_path = path + [nxt]
            if nxt == goal:
                return new_path
            seen.add(nxt)
            frontier.append(new_path)
    return None


@dataclass(slots=True)
class RetryPolicy:
    operation: str
    max_attempts: int
    backoff_strategy: str
    retryable_errors: list[str]
    ambiguity_policy: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ExecutionEvent:
    state: str
    recorded_at: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ExecutionRecord:
    execution_id: str
    strategy_id: str
    strategy_version: str
    signal_id: str
    idempotency_key: str
    state: str
    broker_order_id: str
    position_ref: str
    state_history: list[dict[str, Any]]
    created_at: str
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ExecutionStateStore:
    """Durable JSON-backed execution timeline used by the runtime and dashboard."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.store_root = self.root / "data" / "execution"

    def create_record(
        self,
        *,
        strategy_id: str,
        strategy_version: str,
        signal_id: str,
        idempotency_key: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ExecutionRecord:
        now = _now_iso()
        execution_id = str(uuid4())
        key = idempotency_key or f"{strategy_id}:{signal_id}:{uuid4().hex[:12]}"
        record = ExecutionRecord(
            execution_id=execution_id,
            strategy_id=strategy_id,
            strategy_version=strategy_version,
            signal_id=signal_id,
            idempotency_key=key,
            state="SIGNAL_RECEIVED",
            broker_order_id="",
            position_ref="",
            state_history=[ExecutionEvent("SIGNAL_RECEIVED", now, metadata or {}).to_dict()],
            created_at=now,
            updated_at=now,
        )
        self._write(record)
        return record

    def load(self, execution_id: str) -> ExecutionRecord:
        payload = json.loads(self._path(execution_id).read_text(encoding="utf-8"))
        return ExecutionRecord(**payload)

    def transition(
        self,
        execution_id: str,
        to_state: str,
        *,
        metadata: dict[str, Any] | None = None,
        broker_order_id: str | None = None,
        position_ref: str | None = None,
    ) -> ExecutionRecord:
        record = self.load(execution_id)
        current = record.state
        target = to_state.strip().upper()
        if target != current:
            allowed = _ALLOWED_TRANSITIONS.get(current, set())
            if target not in allowed:
                raise ValueError(f"illegal execution transition: {current} -> {target}")
            record.state = target
            record.state_history.append(ExecutionEvent(target, _now_iso(), metadata or {}).to_dict())
        if broker_order_id is not None:
            record.broker_order_id = broker_order_id
        if position_ref is not None:
            record.position_ref = position_ref
        record.updated_at = _now_iso()
        self._write(record)
        return record

    def recover_incomplete(self) -> list[ExecutionRecord]:
        records: list[ExecutionRecord] = []
        for path in sorted(self.store_root.glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            record = ExecutionRecord(**payload)
            if record.state not in TERMINAL_STATES:
                records.append(record)
        return records

    def advance_to_terminal(
        self,
        execution_id: str,
        terminal: str = "COMPLETED",
        *,
        metadata: dict[str, Any] | None = None,
    ) -> ExecutionRecord:
        """Walk the shortest valid path from the record's current state to
        `terminal`, applying each transition in the state machine. Used by
        startup reconciliation to resolve a record salvaged from an
        interrupted run without bypassing the transition rules (e.g. a record
        stuck at PARTIALLY_FILLED cannot jump straight to FAILED_TERMINAL —
        it must pass through RECOVERY_PENDING first)."""
        record = self.load(execution_id)
        path = _shortest_path(record.state, terminal)
        if path is None:
            raise ValueError(f"no valid transition path from {record.state} to {terminal}")
        for state in path[1:]:
            record = self.transition(
                execution_id, state,
                metadata=metadata if state == path[-1] else None,
            )
        return record

    def timeline(self, execution_id: str) -> list[dict[str, Any]]:
        return list(self.load(execution_id).state_history)

    def count_by_state(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for path in sorted(self.store_root.glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            state = str(payload.get("state", "UNKNOWN"))
            counts[state] = counts.get(state, 0) + 1
        return counts

    def _path(self, execution_id: str) -> Path:
        return self.store_root / f"{execution_id}.json"

    def _write(self, record: ExecutionRecord) -> None:
        self.store_root.mkdir(parents=True, exist_ok=True)
        self._path(record.execution_id).write_text(
            json.dumps(record.to_dict(), indent=2, sort_keys=True),
            encoding="utf-8",
        )
