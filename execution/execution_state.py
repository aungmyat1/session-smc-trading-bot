from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _time_bucket(timestamp: str | None, bucket_seconds: int) -> str:
    """Floor an ISO timestamp to a `bucket_seconds`-wide window, expressed as
    a stable string. Two intent identities built from timestamps in the same
    bucket collide by design (they're treated as the same underlying signal);
    a timestamp in the next bucket gets a distinct identity. Missing/
    unparseable timestamps fall back to a fixed sentinel bucket rather than
    "now" — using wall-clock time here would make two calls for the exact
    same signal collide or not collide depending on when each call happened,
    which defeats the purpose of a deterministic identity."""
    if not timestamp:
        return "no-timestamp"
    try:
        dt = datetime.fromisoformat(str(timestamp))
    except ValueError:
        return f"unparseable:{timestamp}"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    epoch = dt.timestamp()
    bucket_start = int(epoch // bucket_seconds) * bucket_seconds
    return str(bucket_start)


def build_intent_identity(
    *,
    strategy_id: str,
    symbol: str,
    direction: str,
    signal_timestamp: str | None,
    trading_session: str = "",
    time_bucket_seconds: int = 60,
) -> str:
    """Deterministic identity for a trading intent.

    Same underlying signal (same strategy/symbol/direction/timestamp bucket/
    session), called any number of times, produces the same identity — this
    is what `ExecutionStateStore.find_active_by_identity()` matches on to
    detect a duplicate submission before a broker order is placed. Two
    genuinely different signals (different bucket, different direction,
    etc.) always produce different identities, so this never blocks a
    legitimate new trade.

    `trading_session` is the trading session label (e.g. "asian", "london",
    "ny_overlap"), not a process/run identifier — a process restart must
    produce the *same* identity for the same signal, otherwise duplicate
    detection would not survive a restart.
    """
    bucket = _time_bucket(signal_timestamp, time_bucket_seconds)
    direction_norm = (direction or "").strip().lower()
    raw = f"{strategy_id}|{symbol}|{direction_norm}|{bucket}|{trading_session}"
    signal_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"{strategy_id}:{symbol}:{direction_norm}:{bucket}:{signal_hash}"


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

    def find_active_by_identity(self, intent_identity: str) -> ExecutionRecord | None:
        """Return the non-terminal record whose `signal_id` equals
        `intent_identity`, or None if no such record exists.

        This is the duplicate-order gate: it is disk-backed (survives
        process restarts, same as `recover_incomplete()`) and matches
        regardless of which non-terminal state the record is in —
        `SUBMISSION_PENDING` (an order still in flight), `RECOVERY_PENDING`
        (ambiguous after an interruption), or `BROKER_ACKNOWLEDGED`/
        `PARTIALLY_FILLED`/`FILLED`/`JOURNALED`/`RECONCILED` (an order the
        broker has already seen) are all treated the same way here: an
        active record already exists for this exact intent, so a caller
        must not create a second one. If more than one non-terminal record
        somehow matches (should not happen under correct operation — this
        method itself is what prevents it), the most recently updated one is
        returned, since it is the most likely to reflect the current
        broker-truth state.
        """
        matches: list[ExecutionRecord] = []
        for path in sorted(self.store_root.glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            record = ExecutionRecord(**payload)
            if record.state not in TERMINAL_STATES and record.signal_id == intent_identity:
                matches.append(record)
        if not matches:
            return None
        return max(matches, key=lambda r: r.updated_at)

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
