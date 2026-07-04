"""
Real-Time Operations Layer — unified event schema + in-process broadcaster.

Owner decision (2026-07-04): no Redis, no separate ws_gateway/dashboard_api
services. This extends the one deployed dashboard backend
(dashboard/status_server.py) instead of introducing new infrastructure or a
second dashboard backend — consistent with this project's "one dashboard
backend" / "prefer extending existing services" principles.

Cross-process reality: the trading runner (scripts/run_st_a2_demo.py) and
this dashboard are separate OS processes. There is no in-memory channel
between them. Event sourcing is therefore poll-based against durable stores
that already exist — Postgres operations.* (execution/operations_recorder.py,
Sprint 2.3) and reports/control_state.json (dashboard/control_state.py) — not
fabricated, not a new source of truth. The browser still gets genuine push
delivery over one WebSocket connection; only the server-side collection is
polling, and that is an explicit, documented tradeoff, not a hidden one.

Event categories map onto BaseEvent.source_system:
    "execution" — TradeEvent (order created/filled, position opened/closed)
    "strategy"  — StrategyEvent (started/stopped/heartbeat/warning)
    "system"    — SystemEvent (broker connect/disconnect, service restart,
                  health degraded, risk/circuit-breaker/emergency-stop)

Public API:
    BaseEvent, make_trade_event, make_strategy_event, make_system_event
    EventBroadcaster().publish(event) / .subscribe() / .unsubscribe()
    EventPoller(broadcaster).poll_once() — one collection pass, call on a loop
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

_log = logging.getLogger("dashboard.events")

# Bounded so a slow/gone client can never grow memory without limit; a full
# queue drops the oldest event for that one client only (see EventBroadcaster
# .publish) — every other subscriber still gets it.
_PER_CLIENT_QUEUE_MAXSIZE = 500


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class BaseEvent:
    event_type: str
    source_system: str  # "execution" | "strategy" | "system"
    payload: dict[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: str = field(default_factory=_now_iso)
    strategy_id: str = ""
    session_id: str = ""
    severity: str = "info"  # "info" | "warning" | "error"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def make_trade_event(event_type: str, *, strategy_id: str, session_id: str, severity: str = "info", **payload: Any) -> BaseEvent:
    return BaseEvent(event_type=event_type, source_system="execution", strategy_id=strategy_id, session_id=session_id, severity=severity, payload=payload)


def make_strategy_event(event_type: str, *, strategy_id: str, session_id: str, severity: str = "info", **payload: Any) -> BaseEvent:
    return BaseEvent(event_type=event_type, source_system="strategy", strategy_id=strategy_id, session_id=session_id, severity=severity, payload=payload)


def make_system_event(event_type: str, *, session_id: str = "", severity: str = "info", **payload: Any) -> BaseEvent:
    return BaseEvent(event_type=event_type, source_system="system", session_id=session_id, severity=severity, payload=payload)


class EventBroadcaster:
    """In-process pub/sub. One asyncio.Queue per connected WebSocket client.
    No Redis, no cross-process channel — see module docstring."""

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue] = set()

    def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=_PER_CLIENT_QUEUE_MAXSIZE)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        self._subscribers.discard(queue)

    def publish(self, event: BaseEvent) -> None:
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                # Never block or crash the publisher for one slow client —
                # drop that client's oldest item and retry once, don't silently
                # skip the new event either.
                try:
                    queue.get_nowait()
                    queue.put_nowait(event)
                except (asyncio.QueueEmpty, asyncio.QueueFull):
                    _log.warning("dropped event for a saturated subscriber queue")

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)


class EventPoller:
    """Collects new events from durable stores and publishes them. Call
    poll_once() on an interval (see status_server.py's background task)."""

    def __init__(self, broadcaster: EventBroadcaster, *, session_id: str = "") -> None:
        self.broadcaster = broadcaster
        self.session_id = session_id
        self._seen_execution_event_ids: set[str] = set()
        self._seen_control_event_keys: set[str] = set()
        self._last_broker_status: str | None = None

    def poll_once(self) -> int:
        """One collection pass across every source. Returns events published.
        Best-effort per source — one source failing must not block another."""
        published = 0
        published += self._poll_operations_events()
        published += self._poll_control_events()
        published += self._poll_broker_transition()
        return published

    def _poll_operations_events(self) -> int:
        try:
            from execution.operations_recorder import get_recent_events
            rows = get_recent_events(limit=50)
        except Exception as exc:
            _log.warning("event poller: operations_recorder unavailable: %s", exc)
            return 0
        count = 0
        for row in reversed(rows):  # oldest-first so subscribers see real order
            key = row.get("created_at", "") + row.get("event_type", "") + str(row.get("payload", {}).get("event_id", ""))
            if key in self._seen_execution_event_ids:
                continue
            self._seen_execution_event_ids.add(key)
            payload = row.get("payload") or row.get("state") or {}
            strategy_id = str(payload.get("strategy_id", "")) if isinstance(payload, dict) else ""
            event_type = row.get("event_type", "execution_event")
            if row.get("type") == "recovery_checkpoint":
                event = make_system_event("recovery_checkpoint", session_id=self.session_id, payload=payload)
            elif event_type in ("execution_result", "intent_received", "risk_decision"):
                event = make_trade_event(event_type, strategy_id=strategy_id, session_id=self.session_id, payload=payload)
            else:
                event = make_system_event(event_type, session_id=self.session_id, payload=payload)
            self.broadcaster.publish(event)
            count += 1
        if len(self._seen_execution_event_ids) > 2000:
            self._seen_execution_event_ids = set(list(self._seen_execution_event_ids)[-1000:])
        return count

    def _poll_control_events(self) -> int:
        try:
            from dashboard.control_state import load_control_state
            state = load_control_state()
        except Exception as exc:
            _log.warning("event poller: control_state unavailable: %s", exc)
            return 0
        count = 0
        for entry in state.get("control_events", []):
            key = f"{entry.get('recorded_at', '')}:{entry.get('action', '')}"
            if key in self._seen_control_event_keys:
                continue
            self._seen_control_event_keys.add(key)
            severity = "warning" if "emergency" in str(entry.get("action", "")) else "info"
            event = make_system_event(
                str(entry.get("action", "control_event")),
                session_id=self.session_id,
                severity=severity,
                actor=entry.get("actor", ""),
                detail=entry.get("detail", {}),
            )
            self.broadcaster.publish(event)
            count += 1
        if len(self._seen_control_event_keys) > 1000:
            self._seen_control_event_keys = set(list(self._seen_control_event_keys)[-500:])
        return count

    def _poll_broker_transition(self) -> int:
        try:
            import json
            from pathlib import Path
            state = json.loads((Path("logs") / "strategy_demo_state.json").read_text())
        except Exception:
            return 0
        status = str(state.get("broker_status", "unknown"))
        if self._last_broker_status is not None and status != self._last_broker_status:
            event = make_system_event(
                "broker_reconnected" if status == "connected" else "broker_disconnected",
                session_id=self.session_id,
                severity="info" if status == "connected" else "warning",
                previous_status=self._last_broker_status,
                current_status=status,
            )
            self.broadcaster.publish(event)
            self._last_broker_status = status
            return 1
        self._last_broker_status = status
        return 0
