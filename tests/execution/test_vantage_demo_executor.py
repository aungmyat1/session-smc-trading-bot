from __future__ import annotations

import pytest

from execution.vantage_demo_executor import VantageDemoExecutor


class _Connector:
    _account = None
    connection = None

    async def reconnect(self) -> None:
        return None


class _Rpc:
    async def get_symbol_price(self, symbol: str) -> dict:
        assert symbol == "XAUUSD-VIP"
        return {"bid": 2340.0, "ask": 2340.3, "time": "2026-07-13T00:00:00Z"}


@pytest.mark.asyncio
async def test_get_price_normalizes_known_broker_symbol_for_gold_spread():
    executor = VantageDemoExecutor(_Connector())  # type: ignore[arg-type]
    executor._rpc = lambda: _Rpc()  # type: ignore[method-assign]

    price = await executor.get_price("XAUUSD-VIP")

    assert price["spread_pips"] == 3.0
