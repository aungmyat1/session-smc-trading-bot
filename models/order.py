from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(slots=True)
class Order:
    """Normalized order object passed to broker backends."""

    id: str
    symbol: str
    direction: str
    order_type: str = "MARKET"
    volume: float = 0.0
    entry_price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    strategy_id: str | None = None
    magic: int = 0
    comment: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
