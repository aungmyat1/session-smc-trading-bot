"""Tests for execution/trade_manager.py (mocked executor — no broker)"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from execution.trade_manager import TradeManager, _MAGIC


def _make_manager(simulated=True):
    executor = MagicMock()
    executor.place_order   = AsyncMock(return_value={"order_id": "SIM-001", "simulated": simulated})
    executor.close_position = AsyncMock(return_value=True)
    executor.modify_position = AsyncMock(return_value=True)
    executor.get_positions  = AsyncMock(return_value=[
        {"id": "POS-1", "symbol": "EURUSD", "direction": "buy",
         "lots": 0.02, "entry": 1.1000, "sl": 1.0950, "tp": 1.1150,
         "profit": 12.5, "magic": _MAGIC},
        {"id": "POS-2", "symbol": "GBPUSD", "direction": "sell",
         "lots": 0.01, "entry": 1.2700, "sl": 1.2750, "tp": 1.2600,
         "profit": -5.0, "magic": 99999},   # different magic — should be filtered
    ])
    return TradeManager(executor), executor


def _signal_ns(side="long"):
    from types import SimpleNamespace
    return SimpleNamespace(
        pair="EURUSD", side=side,
        entry=1.1000, stop_loss=1.0950, take_profit=1.1150,
    )


class TestTradeManager:
    @pytest.mark.asyncio
    async def test_open_position_calls_executor(self):
        mgr, ex = _make_manager()
        _result = await mgr.open_position(_signal_ns("long"), 0.02)
        ex.place_order.assert_called_once()
        call_kwargs = ex.place_order.call_args.kwargs
        assert call_kwargs["direction"] == "buy"
        assert call_kwargs["lots"] == 0.02

    @pytest.mark.asyncio
    async def test_open_short_maps_to_sell(self):
        mgr, ex = _make_manager()
        await mgr.open_position(_signal_ns("short"), 0.01)
        assert ex.place_order.call_args.kwargs["direction"] == "sell"

    @pytest.mark.asyncio
    async def test_open_position_has_opened_at(self):
        mgr, _ = _make_manager()
        result = await mgr.open_position(_signal_ns(), 0.02)
        assert "opened_at" in result

    @pytest.mark.asyncio
    async def test_close_position_calls_executor(self):
        mgr, ex = _make_manager()
        ok = await mgr.close_position("POS-1")
        ex.close_position.assert_called_once_with("POS-1")
        assert ok is True

    @pytest.mark.asyncio
    async def test_modify_sl_tp_calls_executor(self):
        mgr, ex = _make_manager()
        await mgr.modify_sl_tp("POS-1", 1.0940, 1.1200)
        ex.modify_position.assert_called_once_with("POS-1", 1.0940, 1.1200)

    @pytest.mark.asyncio
    async def test_get_positions_filters_by_magic(self):
        mgr, _ = _make_manager()
        positions = await mgr.get_positions()
        assert len(positions) == 1
        assert positions[0]["id"] == "POS-1"

    @pytest.mark.asyncio
    async def test_emergency_close_all_closes_managed_positions(self):
        mgr, ex = _make_manager()
        count = await mgr.emergency_close_all()
        assert count == 1  # only POS-1 has correct magic
        ex.close_position.assert_called_once_with("POS-1")
