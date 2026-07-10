"""
Telegram alerts — fire-and-forget async messages.

All sends are best-effort: errors are logged, never re-raised, so a Telegram
outage never crashes the bot.
"""

from __future__ import annotations

import hashlib
import logging
import os
import time
from typing import Optional

import aiohttp

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"
TELEGRAM_TEXT_LIMIT = 4096


def _escape_markdown(text: str) -> str:
    """Escape Telegram Markdown metacharacters in dynamic fields."""
    escaped = str(text)
    for char in ("\\", "_", "*", "`", "["):
        escaped = escaped.replace(char, f"\\{char}")
    return escaped


def _clip_text(text: str, limit: int = TELEGRAM_TEXT_LIMIT) -> str:
    if len(text) <= limit:
        return text
    suffix = "\n\n...[truncated]"
    return text[: max(0, limit - len(suffix))] + suffix


class TelegramAlerter:
    def __init__(self, token: Optional[str] = None, chat_id: Optional[str] = None):
        self._token = token or os.getenv("TELEGRAM_BOT_TOKEN", "")
        self._chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID", "")
        self._session: Optional[aiohttp.ClientSession] = None
        self._alert_base_cooldown_s = int(os.getenv("TELEGRAM_ALERT_COOLDOWN_S", "900"))
        self._alert_max_cooldown_s = int(os.getenv("TELEGRAM_ALERT_MAX_COOLDOWN_S", "3600"))
        self._alert_state: dict[str, tuple[float, int]] = {}

    async def start(self) -> None:
        if self._session and not self._session.closed:
            return
        self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10))

    async def stop(self) -> None:
        if self._session:
            await self._session.close()
        self._session = None

    async def send(self, text: str) -> None:
        """Send plain-text message (no Markdown parsing — safe for arbitrary strings)."""
        await self._post(text, parse_mode=None)

    async def _send_md(self, text: str) -> None:
        """Send Markdown-formatted message (used only by typed helpers with known-safe text)."""
        await self._post(text, parse_mode="Markdown")

    def _should_suppress(self, category: str, text: str, parse_mode: "str | None", suppress_key: str | None = None) -> bool:
        key_source = suppress_key or text
        key_raw = f"{category}:{parse_mode or 'plain'}:{key_source}"
        key = hashlib.sha256(key_raw.encode("utf-8")).hexdigest()
        now = time.monotonic()
        last_sent, repeat_count = self._alert_state.get(key, (0.0, 0))
        cooldown = min(self._alert_max_cooldown_s, self._alert_base_cooldown_s * (2 ** repeat_count))
        if last_sent and (now - last_sent) < cooldown:
            remaining = int(cooldown - (now - last_sent))
            logger.info("Telegram alert suppressed for %ss (category=%s)", remaining, category)
            return True
        self._alert_state[key] = (now, repeat_count + 1)
        return False

    @staticmethod
    def _persist(category: str, text: str, *, sent: bool) -> None:
        """Best-effort persistence into operations.execution_event
        (SYSTEM2_MASTER_PLAN.md Phase 3) — lazy, defensive import so this
        alerting module has no hard dependency on the execution package and
        keeps working (alerts still send) even if that import ever fails.
        Called before the actual Telegram network call, per "persist before
        or alongside sending"; never allowed to block or fail a send."""
        try:
            from execution.operations_recorder import record_telegram_alert
            record_telegram_alert(category, text, sent=sent)
        except Exception as exc:
            logger.debug("Telegram alert persistence skipped: %s", exc)

    async def _post(
        self,
        text: str,
        parse_mode: "str | None",
        alert_category: str | None = None,
        suppress_key: str | None = None,
    ) -> None:
        text = _clip_text(text)
        category = alert_category or "generic"
        if not self._token or not self._chat_id:
            logger.debug("Telegram not configured — skipping alert")
            self._persist(category, text, sent=False)
            return
        if alert_category and self._should_suppress(alert_category, text, parse_mode, suppress_key=suppress_key):
            self._persist(category, text, sent=False)
            return
        self._persist(category, text, sent=True)
        if not self._session or self._session.closed:
            await self.start()
        url = TELEGRAM_API.format(token=self._token)
        payload: dict = {"chat_id": self._chat_id, "text": text}
        if parse_mode:
            payload["parse_mode"] = parse_mode
        try:
            async with self._session.post(url, json=payload) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    logger.warning("Telegram send failed %d: %s", resp.status, body[:200])
        except Exception as e:
            logger.warning("Telegram send error: %s", e)

    # ── Typed alert helpers ──────────────────────────────────────────────────

    async def send_startup(
        self,
        pairs: list[str],
        risk_pct: float,
        live: bool,
        recovery_summary: str | None = None,
    ) -> None:
        mode = "🟡 DEMO / DRY RUN" if not live else "🔴 LIVE"
        pairs_str = "\n".join(f"  • {p}" for p in pairs)
        recovery_block = f"\n*Recovery:*\n{recovery_summary}" if recovery_summary else ""
        msg = (
            f"*SMC-Forex-Bot ONLINE* {mode}\n\n"
            f"*Pairs:*\n{pairs_str}\n\n"
            f"*Risk per trade:* {risk_pct}%\n"
            f"*Sessions:* London 07-10 UTC | NY 13-16 UTC"
            f"{recovery_block}"
        )
        await self._send_md(msg)

    async def send_trade_open(
        self,
        symbol: str,
        direction: str,
        entry: float,
        sl: float,
        tp: float,
        risk_pct: float,
        lot: float,
        dry_run: bool = False,
    ) -> None:
        label = "📋 DRY RUN — " if dry_run else ""
        emoji = "🟢 LONG" if direction == "long" else "🔴 SHORT"
        symbol_safe = _escape_markdown(symbol)
        msg = (
            f"{label}*{emoji} {symbol_safe}*\n\n"
            f"Entry: `{entry:.5f}`\n"
            f"SL:    `{sl:.5f}`\n"
            f"TP:    `{tp:.5f}`\n\n"
            f"Risk: {risk_pct}%  |  Lot: {lot}"
        )
        await self._send_md(msg)

    async def send_signal_detected(
        self,
        *,
        strategy: str,
        symbol: str,
        direction: str,
        session: str,
        entry: float,
        stop_loss: float,
        take_profit: float,
        confidence: float,
    ) -> None:
        symbol_safe = _escape_markdown(symbol)
        strategy_safe = _escape_markdown(strategy)
        session_safe = _escape_markdown(session)
        direction_label = "LONG" if direction.lower() in {"long", "buy"} else "SHORT"
        msg = (
            f"📡 *SIGNAL {symbol_safe}*\\n\\n"
            f"Strategy: {strategy_safe}\\n"
            f"Direction: *{direction_label}*\\n"
            f"Session: {session_safe}\\n"
            f"Entry: `{entry:.5f}`\\n"
            f"SL: `{stop_loss:.5f}`\\n"
            f"TP: `{take_profit:.5f}`\\n"
            f"Confidence: `{confidence:.2f}`"
        )
        await self._send_md(msg)

    async def send_trade_close(
        self,
        symbol: str,
        direction: str,
        result_r: float,
        reason: str = "",
    ) -> None:
        emoji = "✅" if result_r >= 0 else "❌"
        sign = "+" if result_r >= 0 else ""
        symbol_safe = _escape_markdown(symbol)
        direction_safe = _escape_markdown(direction.upper())
        reason_safe = _escape_markdown(reason)
        msg = (
            f"{emoji} *CLOSED {symbol_safe}* ({direction_safe})\n\n"
            f"Result: `{sign}{result_r:.2f}R`"
            + (f"\nReason: {reason_safe}" if reason else "")
        )
        await self._send_md(msg)

    async def send_daily_summary(
        self,
        *,
        opened: int,
        closed: int,
        wins: int,
        losses: int,
        avg_r: float,
    ) -> None:
        msg = (
            "[DAILY SUMMARY]\n"
            f"opened={opened}  closed={closed}\n"
            f"wins={wins}  losses={losses}\n"
            f"avg_r={avg_r:.3f}"
        )
        await self._post(
            msg,
            parse_mode=None,
            alert_category="daily_summary",
            suppress_key="daily_summary",
        )

    async def send_circuit_breaker(self, reason: str, state_summary: str) -> None:
        reason_safe = _escape_markdown(reason)
        summary_safe = _escape_markdown(state_summary)
        msg = (
            f"🚨 *CIRCUIT BREAKER ACTIVATED*\n\n"
            f"Reason: `{reason_safe}`\n\n"
            f"State: {summary_safe}\n\n"
            f"Trading halted. Resumes on next daily/weekly reset."
        )
        await self._post(
            msg,
            parse_mode="Markdown",
            alert_category="circuit_breaker",
            suppress_key="circuit_breaker",
        )

    async def send_error(self, error: str) -> None:
        msg = f"⚠️ Bot Error\n\n{str(error)[:1000]}"
        normalized = str(error).split(":", 1)[0].strip().lower() or "error"
        await self._post(
            msg,
            parse_mode=None,
            alert_category="error",
            suppress_key=normalized,
        )

    async def send_emergency_stop(self, *, reason: str, activated_at: str, positions_closed: int) -> None:
        msg = (
            "[EMERGENCY STOP ACTIVE]\n"
            f"activated_at={activated_at}\n"
            f"reason={reason}\n"
            f"positions_closed={positions_closed}"
        )
        await self._post(
            msg,
            parse_mode=None,
            alert_category="emergency_stop",
            suppress_key=activated_at or "emergency_stop",
        )

    async def send_reconciliation_mismatch(self, summary: str) -> None:
        await self._post(
            f"[RECONCILIATION MISMATCH]\n{summary}",
            parse_mode=None,
            alert_category="reconciliation_mismatch",
            suppress_key=summary,
        )

    async def send_session_open(self, session: str) -> None:
        await self.send(f"[{session.upper()} session open] scanning pairs")

    async def send_session_close(self, session: str, closed_count: int) -> None:
        suffix = f" — {closed_count} position(s) closed" if closed_count else ""
        await self.send(f"[{session.upper()} session closed]{suffix}")

    async def send_heartbeat(
        self,
        *,
        timestamp_label: str,
        uptime_s: int,
        connection_status: str,
        live_trading: bool,
        balance: float,
        equity: float,
        open_positions: int,
        last_signal: str,
    ) -> None:
        msg = (
            f"[HEARTBEAT] {timestamp_label}\n"
            f"uptime={uptime_s}s  connection_status={connection_status}  live={live_trading}\n"
            f"balance={balance:.2f}  equity={equity:.2f}  open_positions={open_positions}\n"
            f"last_signal={last_signal}"
        )
        await self._post(
            msg,
            parse_mode=None,
            alert_category="heartbeat",
            suppress_key=f"{connection_status.lower()}:{live_trading}",
        )

    async def send_watchdog_critical(self, *, age_s: float, threshold_s: int) -> None:
        await self._post(
            f"[CRITICAL] No heartbeat for {age_s:.0f}s "
            f"(threshold={threshold_s}s) — bot may be hung",
            parse_mode=None,
            alert_category="watchdog_critical",
            suppress_key="watchdog_critical",
        )

    async def send_reconnect_success(self, source: str = "MetaAPI") -> None:
        await self._post(
            f"[{source} reconnect] restored connection successfully",
            parse_mode=None,
            alert_category="reconnect_success",
            suppress_key=str(source).lower(),
        )

    async def send_reconnect_failure(self, source: str = "MetaAPI", reason: str = "") -> None:
        suffix = f": {reason}" if reason else ""
        await self._post(
            f"[{source} reconnect] failed{suffix}",
            parse_mode=None,
            alert_category="reconnect_failure",
            suppress_key=str(source).lower(),
        )

    async def send_validation_started(self, *, session_id: str, broker: str, account: str) -> None:
        await self._post(
            f"[VALIDATION STARTED] session={session_id} broker={broker} account={account}",
            parse_mode=None,
            alert_category="validation_started",
            suppress_key=session_id,
        )

    async def send_validation_failure(self, *, session_id: str, stage: str, error: str) -> None:
        await self._post(
            f"[VALIDATION FAILURE] session={session_id} stage={stage} error={error[:500]}",
            parse_mode=None,
            alert_category="validation_failure",
            suppress_key=f"{session_id}:{stage}",
        )

    async def send_validation_summary(
        self, *, session_id: str, trade_count: int, success_rate: float | None
    ) -> None:
        rate_label = f"{success_rate:.2%}" if success_rate is not None else "n/a"
        await self._post(
            f"[VALIDATION SUMMARY] session={session_id} trades={trade_count} success_rate={rate_label}",
            parse_mode=None,
            alert_category="validation_summary",
            suppress_key=session_id,
        )
