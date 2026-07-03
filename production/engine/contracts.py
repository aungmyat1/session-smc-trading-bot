"""Stable, broker-neutral contracts for the System 2 execution machine."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, AsyncIterator, Mapping, Protocol


RUNTIME_API_VERSION = "system2-runtime/v1"


class SignalAction(StrEnum):
    BUY = "BUY"
    SELL = "SELL"
    CLOSE = "CLOSE"
    NONE = "NONE"


@dataclass(frozen=True, slots=True)
class MarketEvent:
    symbol: str
    timestamp: datetime
    bid: float
    ask: float
    timeframe: str = "tick"
    payload: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ExecutionSignal:
    action: SignalAction
    symbol: str
    timestamp: datetime
    signal_id: str
    stop_loss: float | None = None
    take_profit: float | None = None
    risk_percent: float | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


class StrategyRuntime(Protocol):
    def on_market_event(self, event: MarketEvent) -> ExecutionSignal: ...


class MarketDataPort(Protocol):
    async def connect(self) -> None: ...
    async def disconnect(self) -> None: ...
    def stream(self) -> AsyncIterator[MarketEvent]: ...
    async def snapshot(self, symbol: str) -> MarketEvent: ...
    async def health(self) -> Mapping[str, Any]: ...


class BrokerPort(Protocol):
    async def account(self) -> Mapping[str, Any]: ...
    async def positions(self) -> list[Mapping[str, Any]]: ...
    async def orders(self) -> list[Mapping[str, Any]]: ...
    async def history(self) -> list[Mapping[str, Any]]: ...
    async def heartbeat(self) -> Mapping[str, Any]: ...


class OrderExecutionPort(Protocol):
    async def place(self, order: Mapping[str, Any]) -> Mapping[str, Any]: ...
    async def cancel(self, order_id: str) -> Mapping[str, Any]: ...
    async def modify(self, order_id: str, changes: Mapping[str, Any]) -> Mapping[str, Any]: ...


class DisabledVantageAdapter:
    """Read surface for Vantage; every write is deterministically unreachable."""

    reason = "BROKER_SUBMISSION_DISABLED"

    async def place(self, order: Mapping[str, Any]) -> Mapping[str, Any]:
        return {"status": "REJECTED_DISABLED", "reason": self.reason, "order": dict(order)}

    async def cancel(self, order_id: str) -> Mapping[str, Any]:
        return {"status": "REJECTED_DISABLED", "reason": self.reason, "order_id": order_id}

    async def modify(self, order_id: str, changes: Mapping[str, Any]) -> Mapping[str, Any]:
        return {"status": "REJECTED_DISABLED", "reason": self.reason, "order_id": order_id, "changes": dict(changes)}
