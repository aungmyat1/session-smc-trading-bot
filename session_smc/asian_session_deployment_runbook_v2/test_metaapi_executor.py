"""
tests/test_metaapi_executor.py
Full mocked test suite for smc_bot/broker/metaapi_executor.py
No real network calls — MetaAPI SDK is patched throughout.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from smc_bot.broker.metaapi_executor import MetaApiExecutor


# ─────────────────────────────────────────────────────────────────────────────
# Shared fixtures
# ─────────────────────────────────────────────────────────────────────────────

CFG = {
    "metaapi": {
        "token": "test_token",
        "account_id": "test_account_id",
        "demo": True,
        "deploy_timeout": 10,
    },
    "risk": {"max_lots_per_symbol": 1.0},
}


def _make_executor(monkeypatch=None) -> MetaApiExecutor:
    ex = MetaApiExecutor(CFG)
    # Inject a pre-built mock connection so connect() is not required in each test
    ex._conn = AsyncMock()
    return ex


# ─────────────────────────────────────────────────────────────────────────────
# connect()
# ─────────────────────────────────────────────────────────────────────────────

class TestConnect:

    @pytest.mark.asyncio
    async def test_connect_success(self):
        mock_account = AsyncMock()
        mock_account.state = "DEPLOYED"
        mock_conn = AsyncMock()
        mock_account.get_streaming_connection.return_value = mock_conn

        mock_api = AsyncMock()
        mock_api.metatrader_account_api.get_account = AsyncMock(return_value=mock_account)

        with patch("smc_bot.broker.metaapi_executor.MetaApi", return_value=mock_api):
            ex = MetaApiExecutor(CFG)
            await ex.connect()

        mock_conn.connect.assert_called_once()
        mock_conn.wait_synchronized.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_raises_without_token(self):
        bad_cfg = {"metaapi": {"token": "", "account_id": "", "demo": True, "deploy_timeout": 10}}
        ex = MetaApiExecutor(bad_cfg)
        with pytest.raises(RuntimeError, match="METAAPI_TOKEN"):
            await ex.connect()

    @pytest.mark.asyncio
    async def test_connect_deploys_if_not_deployed(self):
        mock_account = AsyncMock()
        mock_account.state = "UNDEPLOYED"
        mock_conn = AsyncMock()
        mock_account.get_streaming_connection.return_value = mock_conn

        mock_api = AsyncMock()
        mock_api.metatrader_account_api.get_account = AsyncMock(return_value=mock_account)

        with patch("smc_bot.broker.metaapi_executor.MetaApi", return_value=mock_api):
            ex = MetaApiExecutor(CFG)
            await ex.connect()

        mock_account.deploy.assert_called_once()


# ─────────────────────────────────────────────────────────────────────────────
# check_connected guard
# ─────────────────────────────────────────────────────────────────────────────

class TestCheckConnected:

    @pytest.mark.asyncio
    async def test_raises_if_not_connected(self):
        ex = MetaApiExecutor(CFG)   # _conn is None
        with pytest.raises(RuntimeError, match="connect()"):
            await ex.get_open_positions()


# ─────────────────────────────────────────────────────────────────────────────
# get_balance
# ─────────────────────────────────────────────────────────────────────────────

class TestGetBalance:

    @pytest.mark.asyncio
    async def test_returns_equity(self):
        ex = _make_executor()
        ex._conn.get_account_information = AsyncMock(
            return_value={"equity": 5000.0, "balance": 4800.0}
        )
        balance = await ex.get_balance()
        assert balance == 5000.0

    @pytest.mark.asyncio
    async def test_falls_back_to_balance(self):
        ex = _make_executor()
        ex._conn.get_account_information = AsyncMock(return_value={"balance": 3200.0})
        balance = await ex.get_balance()
        assert balance == 3200.0


# ─────────────────────────────────────────────────────────────────────────────
# place_market_order
# ─────────────────────────────────────────────────────────────────────────────

class TestPlaceMarketOrder:

    @pytest.mark.asyncio
    async def test_buy_order(self):
        ex = _make_executor()
        ex._conn.create_market_buy_order = AsyncMock(
            return_value={"positionId": "pos_001"}
        )
        result = await ex.place_market_order(
            symbol="EURUSD", side="long", volume=0.10,
            sl=1.0980, tp=1.1100, comment="asian_sweep",
        )
        ex._conn.create_market_buy_order.assert_called_once_with(
            "EURUSD", 0.10,
            stop_loss=1.0980, take_profit=1.1100,
            options={"comment": "asian_sweep"},
        )
        assert result["positionId"] == "pos_001"

    @pytest.mark.asyncio
    async def test_sell_order(self):
        ex = _make_executor()
        ex._conn.create_market_sell_order = AsyncMock(
            return_value={"positionId": "pos_002"}
        )
        result = await ex.place_market_order(
            symbol="GBPUSD", side="short", volume=0.05,
            sl=1.2700, tp=1.2400, comment="london_range",
        )
        ex._conn.create_market_sell_order.assert_called_once()
        assert result["positionId"] == "pos_002"

    @pytest.mark.asyncio
    async def test_volume_rounded_to_2dp(self):
        ex = _make_executor()
        ex._conn.create_market_buy_order = AsyncMock(return_value={"positionId": "p"})
        await ex.place_market_order("EURUSD", "long", 0.123456, 1.09, 1.11)
        call_args = ex._conn.create_market_buy_order.call_args
        assert call_args.args[1] == 0.12   # rounded down


# ─────────────────────────────────────────────────────────────────────────────
# place_limit_order
# ─────────────────────────────────────────────────────────────────────────────

class TestPlaceLimitOrder:

    @pytest.mark.asyncio
    async def test_limit_buy(self):
        ex = _make_executor()
        ex._conn.create_limit_buy_order = AsyncMock(return_value={"orderId": "ord_001"})
        result = await ex.place_limit_order(
            "EURUSD", "long", 0.10, price=1.0990, sl=1.0970, tp=1.1100
        )
        ex._conn.create_limit_buy_order.assert_called_once()
        assert result["orderId"] == "ord_001"

    @pytest.mark.asyncio
    async def test_limit_sell(self):
        ex = _make_executor()
        ex._conn.create_limit_sell_order = AsyncMock(return_value={"orderId": "ord_002"})
        await ex.place_limit_order(
            "XAUUSD", "short", 0.05, price=1920.0, sl=1930.0, tp=1880.0
        )
        ex._conn.create_limit_sell_order.assert_called_once()


# ─────────────────────────────────────────────────────────────────────────────
# place_reduce_only (partial close)
# ─────────────────────────────────────────────────────────────────────────────

class TestPlaceReduceOnly:

    @pytest.mark.asyncio
    async def test_partial_close_called(self):
        ex = _make_executor()
        ex._conn.close_position_partially = AsyncMock(return_value={"result": "ok"})
        await ex.place_reduce_only("pos_abc", 0.075, comment="first_close_sweep")
        ex._conn.close_position_partially.assert_called_once_with("pos_abc", 0.08)

    @pytest.mark.asyncio
    async def test_volume_rounded(self):
        ex = _make_executor()
        ex._conn.close_position_partially = AsyncMock(return_value={})
        await ex.place_reduce_only("pos_xyz", 0.07499)
        call_vol = ex._conn.close_position_partially.call_args.args[1]
        assert call_vol == round(0.07499, 2)


# ─────────────────────────────────────────────────────────────────────────────
# set_sl / set_tp
# ─────────────────────────────────────────────────────────────────────────────

class TestModifyPosition:

    @pytest.mark.asyncio
    async def test_set_sl(self):
        ex = _make_executor()
        ex._conn.modify_position = AsyncMock(return_value={"result": "ok"})
        await ex.set_sl("pos_001", 1.0990)
        ex._conn.modify_position.assert_called_once_with("pos_001", stop_loss=1.0990)

    @pytest.mark.asyncio
    async def test_set_tp(self):
        ex = _make_executor()
        ex._conn.modify_position = AsyncMock(return_value={"result": "ok"})
        await ex.set_tp("pos_001", 1.1200)
        ex._conn.modify_position.assert_called_once_with("pos_001", take_profit=1.1200)


# ─────────────────────────────────────────────────────────────────────────────
# get_open_positions / get_positions_for_symbol
# ─────────────────────────────────────────────────────────────────────────────

class TestGetPositions:

    @pytest.mark.asyncio
    async def test_get_open_positions(self):
        ex = _make_executor()
        mock_positions = [
            {"id": "p1", "symbol": "EURUSD", "volume": 0.10},
            {"id": "p2", "symbol": "XAUUSD", "volume": 0.05},
        ]
        ex._conn.get_positions = AsyncMock(return_value=mock_positions)
        result = await ex.get_open_positions()
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_get_positions_for_symbol_filters(self):
        ex = _make_executor()
        ex._conn.get_positions = AsyncMock(return_value=[
            {"id": "p1", "symbol": "EURUSD"},
            {"id": "p2", "symbol": "XAUUSD"},
            {"id": "p3", "symbol": "EURUSD"},
        ])
        result = await ex.get_positions_for_symbol("EURUSD")
        assert len(result) == 2
        assert all(p["symbol"] == "EURUSD" for p in result)

    @pytest.mark.asyncio
    async def test_empty_positions_returns_empty_list(self):
        ex = _make_executor()
        ex._conn.get_positions = AsyncMock(return_value=None)
        result = await ex.get_open_positions()
        assert result == []


# ─────────────────────────────────────────────────────────────────────────────
# close_position
# ─────────────────────────────────────────────────────────────────────────────

class TestClosePosition:

    @pytest.mark.asyncio
    async def test_close_called(self):
        ex = _make_executor()
        ex._conn.close_position = AsyncMock(return_value={"result": "ok"})
        await ex.close_position("pos_001")
        ex._conn.close_position.assert_called_once_with("pos_001")


# ─────────────────────────────────────────────────────────────────────────────
# get_current_price
# ─────────────────────────────────────────────────────────────────────────────

class TestGetCurrentPrice:

    @pytest.mark.asyncio
    async def test_returns_bid_ask_mid(self):
        ex = _make_executor()
        ex._conn.get_symbol_price = AsyncMock(
            return_value={"bid": 1.1000, "ask": 1.1002}
        )
        price = await ex.get_current_price("EURUSD")
        assert price["bid"] == 1.1000
        assert price["ask"] == 1.1002
        assert price["mid"] == pytest.approx(1.1001, rel=1e-5)


# ─────────────────────────────────────────────────────────────────────────────
# get_today_closed_pnl
# ─────────────────────────────────────────────────────────────────────────────

class TestTodayClosedPnl:

    @pytest.mark.asyncio
    async def test_sums_trade_profits(self):
        ex = _make_executor()
        deals = [
            {"type": "DEAL_TYPE_SELL", "profit": 50.0},
            {"type": "DEAL_TYPE_BUY",  "profit": -30.0},
            {"type": "DEAL_TYPE_BALANCE", "profit": 1000.0},  # should be excluded
        ]
        ex._conn.get_deals_by_time_range = AsyncMock(return_value=deals)
        pnl = await ex.get_today_closed_pnl()
        assert pnl == pytest.approx(20.0, rel=1e-5)   # 50 - 30, balance excluded
