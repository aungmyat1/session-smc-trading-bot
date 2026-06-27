from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(slots=True)
class VirtualOrder:
    order_id: str
    symbol: str
    direction: str
    volume: float
    stop_loss: float
    take_profit: float
    requested_at: datetime
    status: str = "pending"
    filled_at: datetime | None = None
    filled_price: float | None = None
    requested_price: float | None = None
    slippage: float = 0.0
    latency_ms: int = 0
    magic: int = 0
    comment: str = ""
    metadata: dict = field(default_factory=dict)


class OrderManager:
    """Track submitted orders during replay."""

    def __init__(self) -> None:
        self._orders: dict[str, VirtualOrder] = {}

    def submit(self, order: VirtualOrder) -> None:
        self._orders[order.order_id] = order

    def get(self, order_id: str) -> VirtualOrder | None:
        return self._orders.get(order_id)

    def update_fill(
        self,
        order_id: str,
        *,
        filled_at: datetime,
        filled_price: float,
        requested_price: float,
        slippage: float,
        latency_ms: int,
    ) -> VirtualOrder:
        order = self._orders[order_id]
        order.status = "filled"
        order.filled_at = filled_at
        order.filled_price = filled_price
        order.requested_price = requested_price
        order.slippage = slippage
        order.latency_ms = latency_ms
        return order

    def mark_rejected(self, order_id: str, reason: str) -> VirtualOrder:
        order = self._orders[order_id]
        order.status = f"rejected:{reason}"
        return order

    def all(self) -> list[VirtualOrder]:
        return list(self._orders.values())

