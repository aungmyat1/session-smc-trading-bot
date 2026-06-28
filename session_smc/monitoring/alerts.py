"""
Telegram fire-and-forget alerter.

Uses TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID from environment / .env file.
All sends are best-effort — failures are logged but never raise.

Usage::
    alerter = TelegramAlerter()
    alerter.send("Signal fired: LONG EURUSD @ 1.08500 | SL=1.08340 | TP1=1.09180")
"""

from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import requests as _requests
    _REQUESTS_AVAILABLE = True
except ImportError:
    _REQUESTS_AVAILABLE = False

TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"


class TelegramAlerter:
    """
    Fire-and-forget Telegram alerter.

    Token and chat ID are read from environment variables at construction time
    so no secrets are hard-coded.
    """

    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None,
    ) -> None:
        self._token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self._chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")

        if not self._token or not self._chat_id:
            logger.warning(
                "TelegramAlerter: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set. "
                "Alerts will be logged only."
            )

    def send(self, message: str, parse_mode: str = "HTML") -> bool:
        """
        Send a message to the configured Telegram chat.

        Returns True on success, False on failure. Never raises.
        """
        if not self._token or not self._chat_id:
            logger.info("[TELEGRAM ALERT - no token] %s", message)
            return False

        if not _REQUESTS_AVAILABLE:
            logger.info("[TELEGRAM ALERT - requests not installed] %s", message)
            return False

        url = TELEGRAM_API_URL.format(token=self._token)
        payload = {
            "chat_id": self._chat_id,
            "text": message,
            "parse_mode": parse_mode,
        }
        try:
            resp = _requests.post(url, json=payload, timeout=5)
            if resp.status_code == 200:
                logger.debug("Telegram alert sent: %s...", message[:80])
                return True
            else:
                logger.error("Telegram send failed: HTTP %d — %s", resp.status_code, resp.text[:200])
                return False
        except Exception as exc:
            logger.error("Telegram send exception: %s", exc)
            return False

    # ------------------------------------------------------------------
    # Convenience methods for standard alert types
    # ------------------------------------------------------------------

    def signal_fired(self, symbol: str, direction: str, entry: float, sl: float, tp1: float) -> bool:
        msg = (
            f"<b>SIGNAL FIRED</b>\n"
            f"Symbol: {symbol} | Dir: {direction}\n"
            f"Entry: {entry:.5f} | SL: {sl:.5f} | TP1: {tp1:.5f}\n"
            f"<i>CONFIRM token required to execute.</i>"
        )
        return self.send(msg)

    def trade_opened(self, symbol: str, direction: str, lots: float, entry: float) -> bool:
        msg = (
            f"<b>TRADE OPENED</b>\n"
            f"{direction} {lots:.2f} lots {symbol} @ {entry:.5f}"
        )
        return self.send(msg)

    def trade_closed(self, symbol: str, result_r: float, result_pips: float) -> bool:
        emoji = "+" if result_r > 0 else "-"
        msg = (
            f"<b>TRADE CLOSED</b>\n"
            f"{symbol}: {emoji}{abs(result_r):.2f}R ({result_pips:+.1f}pip)"
        )
        return self.send(msg)

    def daily_loss_halt(self, daily_loss_r: float, max_r: float) -> bool:
        msg = (
            f"<b>DAILY LOSS HALT</b>\n"
            f"Loss {daily_loss_r:.2f}R hit limit {max_r:.1f}R. Trading halted for today."
        )
        return self.send(msg)

    def drawdown_kill(self, drawdown_pct: float) -> bool:
        msg = (
            f"<b>KILL SWITCH TRIGGERED</b>\n"
            f"Drawdown {drawdown_pct:.1f}% hit max. All trading stopped. Operator review required."
        )
        return self.send(msg)

    def session_close_with_open(self, symbol: str, session: str) -> bool:
        msg = (
            f"<b>SESSION END — OPEN POSITION</b>\n"
            f"{symbol} still open at {session} session end. Auto-closing at market."
        )
        return self.send(msg)

    def bot_error(self, error: str) -> bool:
        msg = f"<b>BOT ERROR</b>\n{error[:500]}"
        return self.send(msg)
