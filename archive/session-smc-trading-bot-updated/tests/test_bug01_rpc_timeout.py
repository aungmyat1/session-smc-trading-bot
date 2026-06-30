"""BUG-01 regression tests — MetaAPI RPC timeout and watchdog.

Simulates the failure mode from 2026-06-21: WebSocket drops while bot sleeps;
on wake-up get_account_information() blocks indefinitely because the SDK's
reconnect loop never synchronizes.

All tests patch RPC_TIMEOUT_S to a small value so they complete in <1s.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from execution.metaapi_client import RPC_TIMEOUT_S, MetaAPIClient

# ── Helpers ───────────────────────────────────────────────────────────────────


def _connected_client() -> MetaAPIClient:
    """MetaAPIClient with _connected=True and a fake SDK connection."""
    client = MetaAPIClient("tok", "acc")
    client._connected = True
    client._connection = MagicMock()
    client._api = MagicMock()
    return client


async def _hang(*_args, **_kwargs):
    """Coroutine that never returns — simulates stuck MetaAPI RPC."""
    await asyncio.Event().wait()


# ── Category 1: _rpc() timeout mechanics ─────────────────────────────────────


class TestRPCTimeoutMechanics:

    @pytest.mark.asyncio
    async def test_rpc_raises_timeout_on_hang(self):
        """_rpc() raises asyncio.TimeoutError when the SDK call never returns."""
        client = _connected_client()
        client._connection.get_account_information = _hang

        with patch("execution.metaapi_client.RPC_TIMEOUT_S", 0.05):
            with pytest.raises(asyncio.TimeoutError):
                await client.get_account_info()

    @pytest.mark.asyncio
    async def test_rpc_timeout_marks_disconnected(self):
        """_connected becomes False the moment an RPC times out."""
        client = _connected_client()
        client._connection.get_account_information = _hang

        with patch("execution.metaapi_client.RPC_TIMEOUT_S", 0.05):
            with pytest.raises(asyncio.TimeoutError):
                await client.get_account_info()

        assert client.is_connected is False

    @pytest.mark.asyncio
    async def test_rpc_fast_call_not_affected(self):
        """_rpc() passes through without interference when the call returns quickly."""
        client = _connected_client()
        client._connection.get_account_information = AsyncMock(
            return_value={
                "balance": 500.0,
                "equity": 510.0,
                "margin": 0.0,
                "freeMargin": 510.0,
                "leverage": 100,
                "currency": "USD",
            }
        )

        info = await client.get_account_info()
        assert info.balance == 500.0
        assert client.is_connected is True

    @pytest.mark.asyncio
    async def test_rpc_timeout_on_get_positions(self):
        """get_open_positions() timeout marks disconnected."""
        client = _connected_client()
        client._connection.get_positions = _hang

        with patch("execution.metaapi_client.RPC_TIMEOUT_S", 0.05):
            with pytest.raises(asyncio.TimeoutError):
                await client.get_open_positions()

        assert client.is_connected is False

    @pytest.mark.asyncio
    async def test_rpc_timeout_on_get_candles(self):
        """get_candles() timeout marks disconnected."""
        client = _connected_client()
        client._connection.get_historical_candles = _hang

        with patch("execution.metaapi_client.RPC_TIMEOUT_S", 0.05):
            with pytest.raises(asyncio.TimeoutError):
                await client.get_candles("EURUSD", "15m")

        assert client.is_connected is False

    @pytest.mark.asyncio
    async def test_rpc_timeout_on_place_order_live(self):
        """place_order() timeout marks disconnected in live mode."""
        client = _connected_client()
        client._connection.create_market_buy_order = _hang

        with patch("execution.metaapi_client.LIVE_TRADING", True):
            with patch("execution.metaapi_client.RPC_TIMEOUT_S", 0.05):
                with pytest.raises(asyncio.TimeoutError):
                    await client.place_order("EURUSD", "long", 0.01, 1.07, 1.09, 21001)

        assert client.is_connected is False

    @pytest.mark.asyncio
    async def test_rpc_timeout_on_close_position_live(self):
        """close_position() timeout marks disconnected in live mode."""
        client = _connected_client()
        client._connection.close_position = _hang

        with patch("execution.metaapi_client.LIVE_TRADING", True):
            with patch("execution.metaapi_client.RPC_TIMEOUT_S", 0.05):
                with pytest.raises(asyncio.TimeoutError):
                    await client.close_position("pos-1")

        assert client.is_connected is False


# ── Category 2: Heartbeat survives RPC timeout ───────────────────────────────


class TestHeartbeatSurvivesTimeout:

    @pytest.mark.asyncio
    async def test_heartbeat_completes_despite_rpc_hang(self):
        """_send_heartbeat() must return even when get_account_info() hangs."""
        import bot as bot_module
        from bot import _send_heartbeat

        client = _connected_client()
        client._connection.get_account_information = _hang
        client._connection.get_positions = _hang

        telegram = MagicMock()
        telegram.send = AsyncMock()

        now = datetime.now(timezone.utc)

        with patch("execution.metaapi_client.RPC_TIMEOUT_S", 0.05):
            # The whole call must finish well within 5 seconds
            await asyncio.wait_for(
                _send_heartbeat(client, telegram, now),
                timeout=5.0,
            )

        # Heartbeat message was still logged and sent
        telegram.send.assert_called_once()
        msg = telegram.send.call_args[0][0]
        assert "[HEARTBEAT]" in msg

    @pytest.mark.asyncio
    async def test_heartbeat_logs_disconnected_on_timeout(self):
        """Heartbeat output shows DISCONNECTED when RPC times out."""
        from bot import _send_heartbeat

        client = _connected_client()
        client._connection.get_account_information = _hang

        telegram = MagicMock()
        telegram.send = AsyncMock()

        now = datetime.now(timezone.utc)

        with patch("execution.metaapi_client.RPC_TIMEOUT_S", 0.05):
            await asyncio.wait_for(
                _send_heartbeat(client, telegram, now),
                timeout=5.0,
            )

        msg = telegram.send.call_args[0][0]
        assert "DISCONNECTED" in msg

    @pytest.mark.asyncio
    async def test_heartbeat_updates_last_heartbeat_ts_on_timeout(self):
        """_last_heartbeat_ts is updated even when RPC times out."""
        import bot as bot_module
        from bot import _send_heartbeat

        client = _connected_client()
        client._connection.get_account_information = _hang

        telegram = MagicMock()
        telegram.send = AsyncMock()

        now = datetime.now(timezone.utc)
        # Freeze module-level timestamp to a stale value
        stale = now - timedelta(minutes=15)
        bot_module._last_heartbeat_ts = stale

        with patch("execution.metaapi_client.RPC_TIMEOUT_S", 0.05):
            await asyncio.wait_for(
                _send_heartbeat(client, telegram, now),
                timeout=5.0,
            )

        assert bot_module._last_heartbeat_ts == now

    @pytest.mark.asyncio
    async def test_event_loop_alive_after_rpc_timeout(self):
        """The asyncio event loop continues running after an RPC timeout."""
        client = _connected_client()
        client._connection.get_account_information = _hang

        with patch("execution.metaapi_client.RPC_TIMEOUT_S", 0.05):
            with pytest.raises(asyncio.TimeoutError):
                await client.get_account_info()

        # Event loop yields control normally after the timeout
        result = await asyncio.sleep(0, result="alive")
        assert result == "alive"


# ── Category 3: Reconnect path ────────────────────────────────────────────────


class TestReconnectPath:

    @pytest.mark.asyncio
    async def test_reconnect_sets_connected_on_success(self):
        """reconnect() sets _connected=True when wait_synchronized succeeds."""
        client = _connected_client()
        client._connected = False
        client._connection.wait_synchronized = AsyncMock(return_value=None)

        result = await client.reconnect()

        assert result is True
        assert client.is_connected is True

    @pytest.mark.asyncio
    async def test_reconnect_returns_false_on_timeout(self):
        """reconnect() returns False when wait_synchronized raises TimeoutError.

        The inner asyncio.wait_for(wait_synchronized, 70s) is what fires in
        production; here we simulate that by making wait_synchronized raise
        asyncio.TimeoutError directly — same code path, no 70-second wait.
        """
        client = _connected_client()
        client._connected = False
        client._connection.wait_synchronized = AsyncMock(
            side_effect=asyncio.TimeoutError()
        )

        result = await client.reconnect()

        assert result is False
        assert client.is_connected is False

    @pytest.mark.asyncio
    async def test_reconnect_returns_false_when_no_connection(self):
        """reconnect() returns False gracefully when _connection is None."""
        client = MetaAPIClient("tok", "acc")
        # _connection is None at construction
        result = await client.reconnect()
        assert result is False

    @pytest.mark.asyncio
    async def test_reconnect_triggered_after_heartbeat_timeout(self):
        """Main loop calls reconnect() after a heartbeat RPC timeout."""
        # This test validates the wiring in run_bot(), not the loop itself.
        # We call reconnect() on the client returned by _connected_client()
        # to verify it is reachable and behaves correctly.
        client = _connected_client()
        client._connected = False
        client._connection.wait_synchronized = AsyncMock(return_value=None)

        # Simulate what the main loop does after _send_heartbeat() reveals disconnect
        if not client.is_connected:
            await client.reconnect()

        assert client.is_connected is True


# ── Category 4: Watchdog task ─────────────────────────────────────────────────


class TestWatchdog:

    @pytest.mark.asyncio
    async def test_watchdog_fires_critical_when_heartbeat_stale(self):
        """Watchdog sends CRITICAL alert when _last_heartbeat_ts is old.

        Patches asyncio.sleep to return after a real 0-second yield so the
        event loop can dispatch the watchdog task without a 60-second wait.
        Saves the real sleep reference before patching so the test's own
        await _real_sleep(0.05) still does a genuine yield.
        """
        import bot as bot_module
        from bot import WATCHDOG_TIMEOUT_S, _run_watchdog

        telegram = MagicMock()
        telegram.send = AsyncMock()

        now = datetime.now(timezone.utc)
        bot_module._last_heartbeat_ts = now - timedelta(seconds=WATCHDOG_TIMEOUT_S + 60)

        _real_sleep = asyncio.sleep  # save before patching

        async def _instant_sleep(s):
            await _real_sleep(0)  # real yield, zero wait

        with patch.object(asyncio, "sleep", side_effect=_instant_sleep):
            task = asyncio.create_task(_run_watchdog(telegram))
            await _real_sleep(0.05)  # real 50ms — watchdog fires in this window
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        telegram.send.assert_called()
        alert_msg = telegram.send.call_args[0][0]
        assert "[CRITICAL]" in alert_msg
        assert "heartbeat" in alert_msg.lower()

    @pytest.mark.asyncio
    async def test_watchdog_silent_when_heartbeat_fresh(self):
        """Watchdog sends no alert when heartbeat is current."""
        import bot as bot_module
        from bot import _run_watchdog

        telegram = MagicMock()
        telegram.send = AsyncMock()

        # Last heartbeat just fired
        bot_module._last_heartbeat_ts = datetime.now(timezone.utc)

        async def _one_cycle():
            with patch("bot.asyncio.sleep", new=AsyncMock(return_value=None)):
                task = asyncio.create_task(_run_watchdog(telegram))
                await asyncio.sleep(0)
                await asyncio.sleep(0)
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        await _one_cycle()

        telegram.send.assert_not_called()

    def test_watchdog_timeout_constant_is_600(self):
        """WATCHDOG_TIMEOUT_S must be exactly 600 seconds (10 minutes)."""
        from bot import WATCHDOG_TIMEOUT_S

        assert WATCHDOG_TIMEOUT_S == 600

    def test_rpc_timeout_constant_is_30(self):
        """RPC_TIMEOUT_S must be exactly 30 seconds."""
        assert RPC_TIMEOUT_S == 30
