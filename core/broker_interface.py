from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BrokerInterface(ABC):
    """Broker contract shared by research, demo, and live execution backends."""

    @abstractmethod
    async def get_account(self) -> Any:
        raise NotImplementedError

    @abstractmethod
    async def get_price(self, symbol: str) -> Any:
        raise NotImplementedError

    @abstractmethod
    async def send_order(self, order: Any) -> Any:
        raise NotImplementedError

    @abstractmethod
    async def modify_order(self, order_id: str, sl: float | None = None, tp: float | None = None) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def close_order(self, order_id: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def get_positions(self) -> list[Any]:
        raise NotImplementedError

