"""Single-position-per-symbol management and reconciliation."""

from __future__ import annotations

from typing import Any, Mapping

from production.engine.orders import OrderService


class PositionService:
    MAGIC = 21099

    def __init__(self, orders: OrderService) -> None:
        self.orders = orders
        self._positions: dict[str, dict[str, Any]] = {}

    async def open(self, position: Mapping[str, Any], *, idempotency_key: str):
        symbol = str(position.get("symbol", ""))
        if not symbol or symbol in self._positions:
            raise PermissionError("one position per symbol is enforced")
        request = {**dict(position), "magic": self.MAGIC}
        result = await self.orders.submit(request, idempotency_key=idempotency_key)
        if result.state in {"FILLED", "PARTIALLY_FILLED"}:
            self._positions[symbol] = {**request, "order_id": result.order_id, "status": result.state}
        return result

    async def close(self, symbol: str):
        position = self._positions.get(symbol)
        if position is None:
            raise KeyError(symbol)
        result = await self.orders.cancel(str(position.get("order_id", "")))
        if result.get("status") in {"CLOSED", "CANCELLED"}:
            self._positions.pop(symbol, None)
        return result

    async def partial_close(self, symbol: str, quantity: float):
        if quantity <= 0:
            raise ValueError("partial close quantity must be positive")
        return await self.orders.modify(str(self._positions[symbol].get("order_id", "")), {"partial_close": quantity})

    async def modify(self, symbol: str, *, stop_loss: float | None = None, take_profit: float | None = None):
        return await self.orders.modify(str(self._positions[symbol].get("order_id", "")), {"stop_loss": stop_loss, "take_profit": take_profit})

    def reconcile(self, broker_positions: list[Mapping[str, Any]]) -> dict[str, Any]:
        local = set(self._positions)
        remote = {str(v.get("symbol", "")) for v in broker_positions if int(v.get("magic", self.MAGIC)) == self.MAGIC}
        return {"consistent": local == remote, "missing_remote": sorted(local - remote), "unknown_remote": sorted(remote - local)}

    def snapshot(self) -> list[dict[str, Any]]:
        return [dict(value) for value in self._positions.values()]
