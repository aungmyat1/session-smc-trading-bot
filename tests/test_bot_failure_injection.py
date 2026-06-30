from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from bot import _connect_with_retry


@pytest.mark.asyncio
async def test_connect_with_retry_recovers_after_transient_failure(monkeypatch):
    client = MagicMock()
    client.connect = AsyncMock(side_effect=[RuntimeError("temporary disconnect"), None])

    telegram = MagicMock()
    telegram.send_error = AsyncMock()

    monkeypatch.setattr("bot.asyncio.sleep", AsyncMock(return_value=None))

    await _connect_with_retry(client, telegram)

    assert client.connect.await_count == 2
    assert telegram.send_error.await_count == 1
    assert "attempt 1 failed" in telegram.send_error.call_args[0][0]


@pytest.mark.asyncio
async def test_connect_with_retry_raises_after_final_failure(monkeypatch):
    client = MagicMock()
    client.connect = AsyncMock(side_effect=RuntimeError("permanent disconnect"))

    telegram = MagicMock()
    telegram.send_error = AsyncMock()

    monkeypatch.setattr("bot._CONNECT_RETRY_MAX", 2)
    monkeypatch.setattr("bot.asyncio.sleep", AsyncMock(return_value=None))

    with pytest.raises(RuntimeError, match="permanent disconnect"):
        await _connect_with_retry(client, telegram)

    assert client.connect.await_count == 2
    assert telegram.send_error.await_count == 1


@pytest.mark.asyncio
async def test_reconnect_alert_helpers_emit_plain_text():
    from monitoring.telegram import TelegramAlerter

    alerter = TelegramAlerter(token="tok", chat_id="chat")
    alerter._post = AsyncMock(return_value=None)  # type: ignore[assignment]

    await alerter.send_reconnect_success("MetaAPI")
    await alerter.send_reconnect_failure("MetaAPI", "during active session")

    assert alerter._post.await_count == 2
    first = alerter._post.call_args_list[0]
    second = alerter._post.call_args_list[1]
    assert "restored connection successfully" in first.args[0]
    assert "failed" in second.args[0]
