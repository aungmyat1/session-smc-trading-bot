"""
Telegram alerts — fire-and-forget async messages.

All sends are best-effort: errors are logged, never re-raised, so a Telegram
outage never crashes the bot.
"""

import logging
import os
from typing import Optional

import aiohttp

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


class TelegramAlerter:
    def __init__(self, token: Optional[str] = None, chat_id: Optional[str] = None):
        self._token = token or os.getenv("TELEGRAM_BOT_TOKEN", "")
        self._chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID", "")
        self._session: Optional[aiohttp.ClientSession] = None

    async def start(self) -> None:
        self._session = aiohttp.ClientSession()

    async def stop(self) -> None:
        if self._session:
            await self._session.close()

    async def send(self, text: str) -> None:
        """Send plain-text message (no Markdown parsing — safe for arbitrary strings)."""
        await self._post(text, parse_mode=None)

    async def _send_md(self, text: str) -> None:
        """Send Markdown-formatted message (used only by typed helpers with known-safe text)."""
        await self._post(text, parse_mode="Markdown")

    async def _post(self, text: str, parse_mode: "str | None") -> None:
        if not self._token or not self._chat_id:
            logger.debug("Telegram not configured — skipping alert")
            return
        if not self._session or self._session.closed:
            self._session = aiohttp.ClientSession()
        url = TELEGRAM_API.format(token=self._token)
        payload: dict = {"chat_id": self._chat_id, "text": text}
        if parse_mode:
            payload["parse_mode"] = parse_mode
        try:
            async with self._session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    logger.warning("Telegram send failed %d: %s", resp.status, body[:200])
        except Exception as e:
            logger.warning("Telegram send error: %s", e)

    # ── Typed alert helpers ──────────────────────────────────────────────────

    async def send_startup(self, pairs: list[str], risk_pct: float, live: bool) -> None:
        mode = "🟡 DEMO / DRY RUN" if not live else "🔴 LIVE"
        pairs_str = "\n".join(f"  • {p}" for p in pairs)
        msg = (
            f"*SMC-Forex-Bot ONLINE* {mode}\n\n"
            f"*Pairs:*\n{pairs_str}\n\n"
            f"*Risk per trade:* {risk_pct}%\n"
            f"*Sessions:* London 07-10 UTC | NY 13-16 UTC"
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
        msg = (
            f"{label}*{emoji} {symbol}*\n\n"
            f"Entry: `{entry:.5f}`\n"
            f"SL:    `{sl:.5f}`\n"
            f"TP:    `{tp:.5f}`\n\n"
            f"Risk: {risk_pct}%  |  Lot: {lot}"
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
        msg = (
            f"{emoji} *CLOSED {symbol}* ({direction.upper()})\n\n"
            f"Result: `{sign}{result_r:.2f}R`"
            + (f"\nReason: {reason}" if reason else "")
        )
        await self._send_md(msg)

    async def send_circuit_breaker(self, reason: str, state_summary: str) -> None:
        msg = (
            f"🚨 *CIRCUIT BREAKER ACTIVATED*\n\n"
            f"Reason: `{reason}`\n\n"
            f"State: {state_summary}\n\n"
            f"Trading halted. Resumes on next daily/weekly reset."
        )
        await self._send_md(msg)

    async def send_error(self, error: str) -> None:
        msg = f"⚠️ Bot Error\n\n{error[:500]}"
        await self.send(msg)

    async def send_session_open(self, session: str) -> None:
        await self.send(f"[{session.upper()} session open] scanning pairs")

    async def send_session_close(self, session: str, closed_count: int) -> None:
        suffix = f" — {closed_count} position(s) closed" if closed_count else ""
        await self.send(f"[{session.upper()} session closed]{suffix}")
