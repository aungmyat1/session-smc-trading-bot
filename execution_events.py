from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(slots=True)
class ExecutionEvent:
    """Broker event emitted for every significant execution state transition."""

    event_id: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    order_id: str = ""
    event_type: str = ""
    price: float | None = None
    message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
