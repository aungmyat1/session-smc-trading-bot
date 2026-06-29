from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from monitoring.telegram import TELEGRAM_TEXT_LIMIT, TelegramAlerter


@pytest.mark.asyncio
async def test_trade_close_escapes_markdown_fields():
    alerter = TelegramAlerter(token="tok", chat_id="chat")
    alerter._post = AsyncMock(return_value=None)  # type: ignore[assignment]

    await alerter.send_trade_close(
        symbol="XAU_USD[demo]",
        direction="long_term",
        result_r=1.25,
        reason="tp_hit_[1]",
    )

    message = alerter._post.call_args.args[0]
    assert "XAU\\_USD\\[demo]" in message
    assert "LONG\\_TERM" in message
    assert "tp\\_hit\\_\\[1]" in message


@pytest.mark.asyncio
async def test_long_messages_are_clipped_to_telegram_limit():
    alerter = TelegramAlerter(token="tok", chat_id="chat")

    class _Response:
        status = 200

        async def text(self) -> str:
            return "ok"

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    captured: dict[str, object] = {}

    class _Session:
        closed = False

        def post(self, url, json):
            captured["url"] = url
            captured["payload"] = json
            return _Response()

        async def close(self):
            self.closed = True

    alerter._session = _Session()  # type: ignore[assignment]
    await alerter.send("x" * (TELEGRAM_TEXT_LIMIT + 200))

    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert len(payload["text"]) <= TELEGRAM_TEXT_LIMIT
    assert payload["text"].endswith("...[truncated]")


@pytest.mark.asyncio
async def test_send_error_suppresses_same_error_family_with_different_details():
    alerter = TelegramAlerter(token="tok", chat_id="chat")
    alerter._post = AsyncMock(side_effect=TelegramAlerter._post.__get__(alerter, TelegramAlerter))  # type: ignore[assignment]

    calls: list[str] = []

    async def _fake_post(text, parse_mode=None, alert_category=None, suppress_key=None):
        calls.append(f"{alert_category}:{suppress_key}:{text}")

    alerter._post = AsyncMock(side_effect=_fake_post)  # type: ignore[assignment]
    await alerter.send_error("MetaAPI reconnect failed: timeout on london-a")
    await alerter.send_error("MetaAPI reconnect failed: timeout on london-b")

    assert alerter._post.await_count == 2

    real = TelegramAlerter(token="tok", chat_id="chat")
    real._session = None
    sent: list[tuple[str | None, str | None]] = []

    async def _capture(text, parse_mode=None, alert_category=None, suppress_key=None):
        if alert_category and real._should_suppress(alert_category, text, parse_mode, suppress_key=suppress_key):
            return
        sent.append((alert_category, suppress_key))

    real._post = AsyncMock(side_effect=_capture)  # type: ignore[assignment]
    await real.send_error("MetaAPI reconnect failed: timeout on london-a")
    await real.send_error("MetaAPI reconnect failed: timeout on london-b")

    assert sent == [("error", "metaapi reconnect failed")]


@pytest.mark.asyncio
async def test_reconnect_helpers_use_category_suppression():
    alerter = TelegramAlerter(token="tok", chat_id="chat")
    seen: list[tuple[str | None, str | None]] = []

    async def _capture(text, parse_mode=None, alert_category=None, suppress_key=None):
        seen.append((alert_category, suppress_key))

    alerter._post = AsyncMock(side_effect=_capture)  # type: ignore[assignment]

    await alerter.send_reconnect_success("MetaAPI")
    await alerter.send_reconnect_failure("MetaAPI", "during active session")

    assert seen == [
        ("reconnect_success", "metaapi"),
        ("reconnect_failure", "metaapi"),
    ]


@pytest.mark.asyncio
async def test_heartbeat_helper_uses_stable_suppression_key():
    alerter = TelegramAlerter(token="tok", chat_id="chat")
    seen: list[tuple[str | None, str | None, str]] = []

    async def _capture(text, parse_mode=None, alert_category=None, suppress_key=None):
        seen.append((alert_category, suppress_key, text))

    alerter._post = AsyncMock(side_effect=_capture)  # type: ignore[assignment]

    await alerter.send_heartbeat(
        timestamp_label="2026-06-29T18:00 UTC",
        uptime_s=300,
        connection_status="CONNECTED",
        live_trading=False,
        balance=1000.0,
        equity=1005.0,
        open_positions=1,
        last_signal="17:45Z",
    )

    assert seen == [
        (
            "heartbeat",
            "connected:False",
            "[HEARTBEAT] 2026-06-29T18:00 UTC\nuptime=300s  connection_status=CONNECTED  live=False\nbalance=1000.00  equity=1005.00  open_positions=1\nlast_signal=17:45Z",
        )
    ]


@pytest.mark.asyncio
async def test_watchdog_helper_uses_dedicated_category():
    alerter = TelegramAlerter(token="tok", chat_id="chat")
    seen: list[tuple[str | None, str | None, str]] = []

    async def _capture(text, parse_mode=None, alert_category=None, suppress_key=None):
        seen.append((alert_category, suppress_key, text))

    alerter._post = AsyncMock(side_effect=_capture)  # type: ignore[assignment]

    await alerter.send_watchdog_critical(age_s=700, threshold_s=600)

    assert seen == [
        (
            "watchdog_critical",
            "watchdog_critical",
            "[CRITICAL] No heartbeat for 700s (threshold=600s) — bot may be hung",
        )
    ]
