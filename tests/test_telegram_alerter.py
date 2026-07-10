from __future__ import annotations

from unittest.mock import AsyncMock, patch

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
    # _post() unconditionally calls _persist() -> record_telegram_alert(),
    # which writes to the real operations.execution_event table unless
    # mocked. Without this patch, every suite run wrote a real "xxxx...
    # [truncated]" row into the live dashboard's event log (found 2026-07-06
    # while verifying Telegram persistence end-to-end for the Production
    # Candidate task — see docs/systems/system2/DASHBOARD_READINESS.md §14).
    with patch("execution.operations_recorder.record_telegram_alert"):
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


@pytest.mark.asyncio
async def test_signal_helper_formats_signal_alert():
    alerter = TelegramAlerter(token="tok", chat_id="chat")
    seen: list[str] = []

    async def _capture(text, parse_mode=None, alert_category=None, suppress_key=None):
        seen.append(text)

    alerter._post = AsyncMock(side_effect=_capture)  # type: ignore[assignment]

    await alerter.send_signal_detected(
        strategy="ST-A2",
        symbol="EURUSD",
        direction="long",
        session="london",
        entry=1.10123,
        stop_loss=1.09901,
        take_profit=1.10789,
        confidence=0.82,
    )

    assert len(seen) == 1
    assert "SIGNAL EURUSD" in seen[0]
    assert "Strategy: ST\\-A2" not in seen[0]
    assert "Confidence: `0.82`" in seen[0]


@pytest.mark.asyncio
async def test_daily_summary_helper_uses_dedicated_category():
    alerter = TelegramAlerter(token="tok", chat_id="chat")
    seen: list[tuple[str | None, str | None, str]] = []

    async def _capture(text, parse_mode=None, alert_category=None, suppress_key=None):
        seen.append((alert_category, suppress_key, text))

    alerter._post = AsyncMock(side_effect=_capture)  # type: ignore[assignment]

    await alerter.send_daily_summary(opened=3, closed=2, wins=1, losses=1, avg_r=0.375)

    assert seen == [
        (
            "daily_summary",
            "daily_summary",
            "[DAILY SUMMARY]\nopened=3  closed=2\nwins=1  losses=1\navg_r=0.375",
        )
    ]


@pytest.mark.asyncio
async def test_validation_started_helper_uses_dedicated_category():
    alerter = TelegramAlerter(token="tok", chat_id="chat")
    seen: list[tuple[str | None, str | None, str]] = []

    async def _capture(text, parse_mode=None, alert_category=None, suppress_key=None):
        seen.append((alert_category, suppress_key, text))

    alerter._post = AsyncMock(side_effect=_capture)  # type: ignore[assignment]

    await alerter.send_validation_started(session_id="val-1", broker="vantage-mt5-demo", account="12345")

    assert seen == [
        (
            "validation_started",
            "val-1",
            "[VALIDATION STARTED] session=val-1 broker=vantage-mt5-demo account=12345",
        )
    ]


@pytest.mark.asyncio
async def test_validation_summary_helper_formats_success_rate():
    alerter = TelegramAlerter(token="tok", chat_id="chat")
    seen: list[str] = []

    async def _capture(text, parse_mode=None, alert_category=None, suppress_key=None):
        seen.append(text)

    alerter._post = AsyncMock(side_effect=_capture)  # type: ignore[assignment]

    await alerter.send_validation_summary(session_id="val-1", trade_count=5, success_rate=0.8)

    assert seen == ["[VALIDATION SUMMARY] session=val-1 trades=5 success_rate=80.00%"]


# ── Alert persistence (SYSTEM2_MASTER_PLAN.md Phase 3, 2026-07-06) ────────────

class _FakeResponse:
    status = 200

    async def text(self) -> str:
        return "ok"

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeSession:
    closed = False

    def post(self, url, json):
        return _FakeResponse()

    async def close(self):
        self.closed = True


@pytest.mark.asyncio
async def test_sent_alert_is_persisted_with_sent_true():
    alerter = TelegramAlerter(token="tok", chat_id="chat")
    alerter._session = _FakeSession()  # type: ignore[assignment]

    with patch("execution.operations_recorder.record_telegram_alert") as mock_persist:
        await alerter.send_circuit_breaker("daily loss limit", "3 consecutive losses")

    mock_persist.assert_called_once()
    args, kwargs = mock_persist.call_args
    assert args[0] == "circuit_breaker"
    assert kwargs.get("sent") is True


@pytest.mark.asyncio
async def test_unconfigured_alerter_still_persists_with_sent_false():
    """No TELEGRAM_BOT_TOKEN/CHAT_ID configured must not skip persistence —
    the underlying operational event still happened and belongs in history
    even though nothing was actually delivered. Sets _token/_chat_id directly
    (bypassing __init__'s `token or os.getenv(...)` fallback, which would
    otherwise pick up any TELEGRAM_BOT_TOKEN already set in this shell)."""
    alerter = TelegramAlerter(token="tok", chat_id="chat")
    alerter._token = ""
    alerter._chat_id = ""

    with patch("execution.operations_recorder.record_telegram_alert") as mock_persist:
        await alerter.send_error("something broke")

    mock_persist.assert_called_once_with("error", "⚠️ Bot Error\n\nsomething broke", sent=False)


@pytest.mark.asyncio
async def test_suppressed_alert_persists_with_sent_false():
    alerter = TelegramAlerter(token="tok", chat_id="chat")
    alerter._session = _FakeSession()  # type: ignore[assignment]

    with patch("execution.operations_recorder.record_telegram_alert") as mock_persist:
        await alerter.send_error("MetaAPI reconnect failed: timeout A")
        await alerter.send_error("MetaAPI reconnect failed: timeout B")  # same family — suppressed

    assert mock_persist.call_count == 2
    first_kwargs = mock_persist.call_args_list[0].kwargs
    second_kwargs = mock_persist.call_args_list[1].kwargs
    assert first_kwargs.get("sent") is True
    assert second_kwargs.get("sent") is False


@pytest.mark.asyncio
async def test_persistence_failure_never_blocks_the_actual_send():
    """A DB hiccup in the persistence path must not prevent the real
    Telegram message from being sent — matches the module's own
    never-block/never-raise contract."""
    alerter = TelegramAlerter(token="tok", chat_id="chat")
    alerter._session = _FakeSession()  # type: ignore[assignment]

    with patch("execution.operations_recorder.record_telegram_alert", side_effect=RuntimeError("db down")):
        await alerter.send("plain alert")  # must not raise — assertion is that we reach here


def test_severity_classification_flags_real_problems_not_all_info():
    from execution.operations_recorder import _classify_event_severity

    assert _classify_event_severity("telegram_alert:error") == "error"
    assert _classify_event_severity("telegram_alert:emergency_stop") == "error"
    assert _classify_event_severity("telegram_alert:circuit_breaker") == "warning"
    assert _classify_event_severity("telegram_alert:heartbeat") == "info"
    assert _classify_event_severity("telegram_alert:daily_summary") == "info"
    assert _classify_event_severity("execution_result") == "info"
    assert _classify_event_severity("intent_rejected") == "error"
