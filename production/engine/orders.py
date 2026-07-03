"""Idempotent order lifecycle over the disabled execution port."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from production.engine.contracts import OrderExecutionPort


@dataclass(slots=True)
class OrderRecord:
    order_id: str
    idempotency_key: str
    state: str
    request: dict[str, Any]
    result: dict[str, Any] = field(default_factory=dict)


class OrderService:
    def __init__(self, execution: OrderExecutionPort) -> None:
        self.execution = execution
        self._by_key: dict[str, OrderRecord] = {}

    async def submit(self, order: Mapping[str, Any], *, idempotency_key: str) -> OrderRecord:
        if not idempotency_key:
            raise ValueError("idempotency key is required")
        existing = self._by_key.get(idempotency_key)
        if existing is not None:
            return existing
        result = dict(await self.execution.place(order))
        record = OrderRecord(str(result.get("order_id", "")), idempotency_key, str(result.get("status", "UNKNOWN")), dict(order), result)
        self._by_key[idempotency_key] = record
        return record

    async def cancel(self, order_id: str) -> Mapping[str, Any]:
        return await self.execution.cancel(order_id)

    async def modify(self, order_id: str, changes: Mapping[str, Any]) -> Mapping[str, Any]:
        return await self.execution.modify(order_id, changes)

    def reconcile(self, broker_orders: list[Mapping[str, Any]]) -> dict[str, Any]:
        local = {r.order_id for r in self._by_key.values() if r.order_id}
        remote = {str(v.get("order_id", v.get("id", ""))) for v in broker_orders}
        missing_remote, unknown_remote = sorted(local - remote), sorted(remote - local - {""})
        return {"consistent": not missing_remote and not unknown_remote, "missing_remote": missing_remote, "unknown_remote": unknown_remote}
