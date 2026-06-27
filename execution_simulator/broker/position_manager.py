from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(slots=True)
class VirtualPosition:
    position_id: str
    order_id: str
    symbol: str
    direction: str
    volume: float
    open_price: float
    stop_loss: float
    take_profit: float
    open_time: datetime
    magic: int = 0
    comment: str = ""
    close_time: datetime | None = None
    close_price: float | None = None
    exit_reason: str = ""
    profit: float = 0.0
    metadata: dict = field(default_factory=dict)

    @property
    def is_open(self) -> bool:
        return self.close_time is None


class PositionManager:
    """Manage open and closed positions inside the virtual broker."""

    def __init__(self, contract_size_by_symbol: dict[str, float] | None = None) -> None:
        self._positions: dict[str, VirtualPosition] = {}
        self.contract_size_by_symbol = contract_size_by_symbol or {"EURUSD": 100_000.0, "GBPUSD": 100_000.0, "XAUUSD": 100.0}

    def open_position(self, position: VirtualPosition) -> None:
        self._positions[position.position_id] = position

    def close_position(self, position_id: str, close_price: float, close_time: datetime, exit_reason: str) -> VirtualPosition:
        position = self._positions[position_id]
        if position.close_time is None:
            position.close_time = close_time
            position.close_price = close_price
            position.exit_reason = exit_reason
            position.profit = self._calculate_profit(position, close_price)
        return position

    def remove_position(self, position_id: str) -> None:
        self._positions.pop(position_id, None)

    def get(self, position_id: str) -> VirtualPosition | None:
        return self._positions.get(position_id)

    def open_positions(self, symbol: str | None = None) -> list[VirtualPosition]:
        items = [p for p in self._positions.values() if p.is_open]
        if symbol is not None:
            items = [p for p in items if p.symbol == symbol]
        return sorted(items, key=lambda p: p.open_time)

    def closed_positions(self) -> list[VirtualPosition]:
        return [p for p in self._positions.values() if not p.is_open]

    def _calculate_profit(self, position: VirtualPosition, close_price: float) -> float:
        contract_size = self.contract_size_by_symbol.get(position.symbol, 100_000.0)
        diff = close_price - position.open_price
        if position.direction.lower() in {"short", "sell"}:
            diff = -diff
        return diff * contract_size * position.volume

