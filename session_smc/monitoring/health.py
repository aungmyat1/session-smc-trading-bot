"""
Health monitor — process heartbeat, broker connectivity, latency tracking.

Usage::
    monitor = HealthMonitor(strategy_id="ST-A2")
    monitor.heartbeat()
    status = monitor.get_status()
    if status.broker_ok is False:
        alert(...)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)
_UTC = timezone.utc

HEARTBEAT_STALE_SECONDS = 60       # Heartbeat older than this = unhealthy
LATENCY_WARNING_MS = 500
LATENCY_CRITICAL_MS = 2000


@dataclass
class HealthStatus:
    strategy_id: str
    timestamp: str
    alive: bool = True
    broker_ok: Optional[bool] = None
    last_heartbeat_age_s: float = 0.0
    last_latency_ms: Optional[float] = None
    consecutive_broker_failures: int = 0
    notes: list[str] = field(default_factory=list)

    @property
    def healthy(self) -> bool:
        if not self.alive:
            return False
        if self.last_heartbeat_age_s > HEARTBEAT_STALE_SECONDS:
            return False
        if self.broker_ok is False:
            return False
        return True

    def to_dict(self) -> dict:
        return {
            "strategy_id": self.strategy_id,
            "timestamp": self.timestamp,
            "alive": self.alive,
            "healthy": self.healthy,
            "broker_ok": self.broker_ok,
            "last_heartbeat_age_s": self.last_heartbeat_age_s,
            "last_latency_ms": self.last_latency_ms,
            "consecutive_broker_failures": self.consecutive_broker_failures,
            "notes": self.notes,
        }


class HealthMonitor:
    """
    Process heartbeat and broker connectivity monitor.

    Thread-safe for single-writer use. For multi-threaded use, wrap in a lock.
    """

    def __init__(self, strategy_id: str = "unknown") -> None:
        self.strategy_id = strategy_id
        self._last_heartbeat: Optional[float] = None
        self._broker_ok: Optional[bool] = None
        self._last_latency_ms: Optional[float] = None
        self._consecutive_broker_failures: int = 0
        self._notes: list[str] = []

    def heartbeat(self) -> None:
        """Call periodically from the main loop to indicate the process is alive."""
        self._last_heartbeat = time.monotonic()

    def record_broker_check(self, ok: bool, latency_ms: Optional[float] = None) -> None:
        """Record the result of a broker connectivity check."""
        self._broker_ok = ok
        self._last_latency_ms = latency_ms
        if ok:
            self._consecutive_broker_failures = 0
        else:
            self._consecutive_broker_failures += 1
            logger.warning(
                "[%s] Broker check failed (consecutive: %d)",
                self.strategy_id,
                self._consecutive_broker_failures,
            )

    def add_note(self, note: str) -> None:
        self._notes.append(f"{datetime.now(_UTC).isoformat()} {note}")
        if len(self._notes) > 100:
            self._notes = self._notes[-100:]

    def get_status(self) -> HealthStatus:
        now = time.monotonic()
        age = (now - self._last_heartbeat) if self._last_heartbeat is not None else float("inf")
        return HealthStatus(
            strategy_id=self.strategy_id,
            timestamp=datetime.now(_UTC).isoformat(),
            alive=self._last_heartbeat is not None,
            broker_ok=self._broker_ok,
            last_heartbeat_age_s=age,
            last_latency_ms=self._last_latency_ms,
            consecutive_broker_failures=self._consecutive_broker_failures,
            notes=list(self._notes[-10:]),
        )
