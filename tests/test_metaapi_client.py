"""Tests for execution/metaapi_client.py — broker connectivity wrapper."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from execution.metaapi_client import MetaAPIClient, AccountInfo, OrderResult


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_client() -> MetaAPIClient:
    return MetaAPIClient("test-token", "test-account-id")


def _connected_client() -> MetaAPIClient:
    """Return a client whose _connected flag is already True and has a mock connection."""
    client = make_client()
    client._connected = True
    client._connection = AsyncMock()
    client._api = MagicMock()
    return client


# ── Category 1: Initial state ─────────────────────────────────────────────────

class TestInitialState:
    def test_not_connected_before_connect(self):
        client = make_client()
        assert client.is_connected is False

    def test_connection_status_before_connect(self):
        client = make_client()
        status = client.connection_status()
        assert status["connected"] is False
        assert "account_id" in status
        assert "live_trading" in status

    def test_get_open_positions_returns_empty_when_not_connected(self):
        import asyncio
        client = make_client()
        positions = asyncio.run(client.get_open_positions())
        assert positions == []

    def test_check_spread_returns_false_when_not_connected(self):
        import asyncio
        client = make_client()
        ok, pips = asyncio.run(client.check_spread("EURUSD"))
        assert ok is False
        assert pips == 0.0

    def test_get_candles_returns_empty_when_not_connected(self):
        import asyncio
        client = make_client()
        bars = asyncio.run(client.get_candles("EURUSD", "15m"))
        assert bars == []


# ── Category 2: Connected state ───────────────────────────────────────────────

class TestConnectedState:
    @pytest.mark.asyncio
    async def test_connect_sets_connected_flag(self):
        client = make_client()
        mock_account = AsyncMock()
        mock_account.state = "DEPLOYED"
        mock_account.wait_connected = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.connect = AsyncMock()
        mock_conn.wait_synchronized = AsyncMock()
        mock_account.get_rpc_connection = MagicMock(return_value=mock_conn)

        mock_api_instance = MagicMock()
        mock_api_instance.metatrader_account_api.get_account = AsyncMock(return_value=mock_account)
        mock_sdk = MagicMock()
        mock_sdk.MetaApi = MagicMock(return_value=mock_api_instance)

        # MetaApi is imported lazily inside connect() — patch via sys.modules
        with patch.dict("sys.modules", {"metaapi_cloud_sdk": mock_sdk}):
            await client.connect()

        assert client.is_connected is True

    @pytest.mark.asyncio
    async def test_disconnect_clears_connected_flag(self):
        client = _connected_client()
        await client.disconnect()
        assert client.is_connected is False

    @pytest.mark.asyncio
    async def test_get_account_info_raises_when_not_connected(self):
        client = make_client()
        with pytest.raises(RuntimeError, match="Not connected"):
            await client.get_account_info()

    @pytest.mark.asyncio
    async def test_get_account_info_returns_account_info(self):
        client = _connected_client()
        client._connection.get_account_information = AsyncMock(return_value={
            "balance": 1000.0, "equity": 1050.0, "margin": 50.0,
            "freeMargin": 1000.0, "leverage": 100, "currency": "USD",
        })
        info = await client.get_account_info()
        assert isinstance(info, AccountInfo)
        assert info.balance == 1000.0
        assert info.equity == 1050.0
        assert info.currency == "USD"

    @pytest.mark.asyncio
    async def test_get_candles_prefers_account_historical_candles(self):
        client = _connected_client()
        client._account = AsyncMock()
        client._account.get_historical_candles = AsyncMock(return_value=[{
            "time": "2026-06-26T00:00:00Z",
            "open": 1.1,
            "high": 1.2,
            "low": 1.0,
            "close": 1.15,
            "tickVolume": 123,
        }])
        client._connection.get_historical_candles = AsyncMock(side_effect=AssertionError("should not use connection fallback"))
        bars = await client.get_candles("EURUSD", "15m", count=1)
        assert len(bars) == 1
        assert bars[0]["close"] == 1.15
        assert bars[0]["volume"] == 123

    @pytest.mark.asyncio
    async def test_get_candles_uses_connection_fallback_when_account_missing(self):
        client = _connected_client()
        client._account = None
        client._connection.get_historical_candles = AsyncMock(side_effect=AttributeError("missing"))
        client._connection.get_candles = AsyncMock(return_value=[{
            "time": "2026-06-26T00:00:00Z",
            "open": 1.1,
            "high": 1.2,
            "low": 1.0,
            "close": 1.15,
            "tickVolume": 55,
        }])
        bars = await client.get_candles("EURUSD", "15m", count=1)
        assert len(bars) == 1
        assert bars[0]["volume"] == 55


# ── Category 3: DRY_RUN mode ──────────────────────────────────────────────────

class TestDryRunMode:
    @pytest.mark.asyncio
    async def test_place_order_returns_dry_run_when_live_trading_false(self):
        client = _connected_client()
        # LIVE_TRADING is read from env; module-level var is False by default in tests
        with patch("execution.metaapi_client.LIVE_TRADING", False):
            result = await client.place_order(
                symbol="EURUSD", direction="long", volume=0.01,
                sl=1.07000, tp=1.09000, magic=21001,
            )
        assert isinstance(result, OrderResult)
        assert result.dry_run is True
        assert result.order_id == "DRY_RUN"
        assert result.symbol == "EURUSD"

    @pytest.mark.asyncio
    async def test_close_position_returns_true_in_dry_run(self):
        client = _connected_client()
        with patch("execution.metaapi_client.LIVE_TRADING", False):
            ok = await client.close_position("pos-123")
        assert ok is True

    @pytest.mark.asyncio
    async def test_place_order_does_not_call_sdk_in_dry_run(self):
        client = _connected_client()
        with patch("execution.metaapi_client.LIVE_TRADING", False):
            await client.place_order("EURUSD", "long", 0.01, 1.07, 1.09, 21001)
        client._connection.create_market_buy_order.assert_not_called()


# ── Category 4: Spread check ──────────────────────────────────────────────────

class TestSpreadCheck:
    @pytest.mark.asyncio
    async def test_spread_ok_for_normal_spread(self):
        client = _connected_client()
        client._connection.get_symbol_price = AsyncMock(return_value={
            "bid": 1.07000, "ask": 1.07010, "time": "2026-01-01T08:00:00Z"
        })
        ok, pips = await client.check_spread("EURUSD")
        assert ok is True
        assert pips == pytest.approx(1.0)

    @pytest.mark.asyncio
    async def test_spread_rejected_for_wide_spread(self):
        client = _connected_client()
        # EURUSD max = 3.0 pips; set ask-bid = 4 pips
        client._connection.get_symbol_price = AsyncMock(return_value={
            "bid": 1.07000, "ask": 1.07040, "time": ""
        })
        ok, pips = await client.check_spread("EURUSD")
        assert ok is False
        assert pips == pytest.approx(4.0)

    @pytest.mark.asyncio
    async def test_spread_check_returns_false_on_exception(self):
        client = _connected_client()
        client._connection.get_symbol_price = AsyncMock(side_effect=Exception("timeout"))
        ok, pips = await client.check_spread("EURUSD")
        assert ok is False


# ── Category 5: Position list ─────────────────────────────────────────────────

class TestPositionList:
    @pytest.mark.asyncio
    async def test_get_open_positions_maps_type_buy_to_long(self):
        client = _connected_client()
        client._connection.get_positions = AsyncMock(return_value=[{
            "id": "p1", "symbol": "EURUSD", "type": "POSITION_TYPE_BUY",
            "volume": 0.01, "openPrice": 1.07, "stopLoss": 1.06,
            "takeProfit": 1.09, "profit": 5.0, "magic": 21001,
        }])
        positions = await client.get_open_positions()
        assert len(positions) == 1
        assert positions[0].direction == "long"

    @pytest.mark.asyncio
    async def test_get_open_positions_filters_by_magic(self):
        client = _connected_client()
        client._connection.get_positions = AsyncMock(return_value=[
            {"id": "p1", "symbol": "EURUSD", "type": "POSITION_TYPE_BUY",
             "volume": 0.01, "openPrice": 1.07, "stopLoss": 0, "takeProfit": 0,
             "profit": 0, "magic": 21001},
            {"id": "p2", "symbol": "GBPUSD", "type": "POSITION_TYPE_SELL",
             "volume": 0.01, "openPrice": 1.27, "stopLoss": 0, "takeProfit": 0,
             "profit": 0, "magic": 21002},
        ])
        positions = await client.get_open_positions(magic=21001)
        assert len(positions) == 1
        assert positions[0].symbol == "EURUSD"


# ── Category 6: Connection failure handling ───────────────────────────────────

class TestConnectionFailure:
    @pytest.mark.asyncio
    async def test_connect_raises_runtime_error_if_sdk_missing(self):
        client = make_client()
        with patch.dict("sys.modules", {"metaapi_cloud_sdk": None}):
            with pytest.raises((RuntimeError, ImportError)):
                await client.connect()

    @pytest.mark.asyncio
    async def test_place_order_raises_when_connected_but_live_and_connection_lost(self):
        client = make_client()
        client._connected = False
        with patch("execution.metaapi_client.LIVE_TRADING", True):
            with pytest.raises(RuntimeError, match="Not connected"):
                await client.place_order("EURUSD", "long", 0.01, 1.07, 1.09, 21001)
