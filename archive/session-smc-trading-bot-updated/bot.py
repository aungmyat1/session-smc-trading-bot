"""
Session Trading Bot — main loop (DEP-01).

Architecture:
    MetaAPIClient  (VT Markets demo account)
        ↓
    get_candles()  M15 + H4 candles per pair
        ↓
    run_strategy() ST-A2 signal chain
        ↓
    OrderManager   validate → size → submit
        ↓
    TradeLogger    JSONL event log
    TelegramAlerter

LIVE_TRADING=false → DRY_RUN mode: connect, receive data, log all orders but never
                     send them to the broker.
LIVE_TRADING=true  → real orders on the connected MT5 account.
                     Set by the owner manually only. Never set by this code.

Health monitor: heartbeat every 5 minutes.
Signal dedup: seen signal timestamps are tracked per symbol; each signal is
              processed at most once per bot run.
"""

import asyncio
import json
import logging
import logging.handlers
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ── Logging ──────────────────────────────────────────────────────────────────

Path("logs").mkdir(exist_ok=True)

_file_handler = logging.handlers.TimedRotatingFileHandler(
    "logs/bot.log",
    when="midnight",
    utc=True,
    backupCount=7,  # keep 7 days of rotated logs
    encoding="utf-8",
)
_file_handler.suffix = "%Y-%m-%d"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        _file_handler,
    ],
)
logger = logging.getLogger("bot")

# ── Config ────────────────────────────────────────────────────────────────────

with open("config/config.json") as f:
    CONFIG = json.load(f)

PAIRS: list[str] = CONFIG["pairs"]
POLL_INTERVAL: int = CONFIG.get("poll_interval_seconds", 60)
LIVE_TRADING: bool = os.getenv("LIVE_TRADING", "false").lower() == "true"

METAAPI_TOKEN: str = os.getenv("METAAPI_TOKEN", "")
METAAPI_ACCOUNT_ID: str = os.getenv("VANTAGE_DEMO_METAAPI_ID", "")
TELEGRAM_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")

HEARTBEAT_INTERVAL_S: int = 300  # 5 minutes
WATCHDOG_TIMEOUT_S: int = 600  # 10 minutes — CRITICAL alert if no heartbeat fires
_BOT_START_TIME: datetime = datetime.now(timezone.utc)
_LAST_SIGNAL_TIME: "datetime | None" = None
_last_heartbeat_ts: datetime = datetime.now(
    timezone.utc
)  # updated each time heartbeat logs

# ── Imports ───────────────────────────────────────────────────────────────────

from data.session_filter import get_active_session, seconds_to_next_session
from execution.metaapi_client import MetaAPIClient
from execution.order_manager import OrderManager
from execution.risk_manager import RiskManager
from execution.trade_logger import TradeLogger
from monitoring.telegram import TelegramAlerter
from strategy.session_liquidity.session_strategy import run_strategy

# ── Main loop ─────────────────────────────────────────────────────────────────


async def run_bot() -> None:
    telegram = TelegramAlerter(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)
    await telegram.start()

    client = MetaAPIClient(METAAPI_TOKEN, METAAPI_ACCOUNT_ID)
    risk = RiskManager(CONFIG)
    trade_logger = TradeLogger()
    order_manager = OrderManager(client, risk, trade_logger, CONFIG)

    # Dedup: track signal timestamps already processed, per symbol
    global _BOT_START_TIME, _LAST_SIGNAL_TIME, _last_heartbeat_ts
    _BOT_START_TIME = datetime.now(timezone.utc)
    _last_heartbeat_ts = _BOT_START_TIME

    seen_signals: dict[str, set[str]] = {sym: set() for sym in PAIRS}

    last_session: "str | None" = None
    last_heartbeat: datetime = datetime.now(timezone.utc)

    watchdog_task = asyncio.create_task(_run_watchdog(telegram))

    try:
        logger.info("Connecting to MetaAPI (LIVE_TRADING=%s)…", LIVE_TRADING)
        await client.connect()
        logger.info("MetaAPI connected.")

        await telegram.send_startup(
            PAIRS, CONFIG["risk"]["risk_per_trade_pct"], LIVE_TRADING
        )

        while True:
            now = datetime.now(timezone.utc)
            session = get_active_session(now)

            # ── Heartbeat (every 5 min) ───────────────────────────────────────
            elapsed = (now - last_heartbeat).total_seconds()
            if elapsed >= HEARTBEAT_INTERVAL_S:
                await _send_heartbeat(client, telegram, now)
                last_heartbeat = now
                if not client.is_connected:
                    logger.info(
                        "Connection lost after heartbeat — attempting reconnect"
                    )
                    await client.reconnect()

            # ── Session boundary ──────────────────────────────────────────────
            if session != last_session:
                if last_session is not None:
                    await _close_session_positions(
                        client, telegram, last_session, CONFIG
                    )
                if session:
                    await telegram.send_session_open(session)
                last_session = session

            # ── Circuit breaker check ─────────────────────────────────────────
            cb = risk.check_circuit_breakers(now)
            if cb.halted:
                logger.warning("Bot halted: %s — sleeping", cb.reason)
                await asyncio.sleep(POLL_INTERVAL)
                continue

            # ── Off-hours: sleep until next session ───────────────────────────
            if not session:
                wait = seconds_to_next_session(now)
                logger.info("Off-hours. Next session in %ds", wait)
                await asyncio.sleep(min(wait, POLL_INTERVAL * 5))
                continue

            # ── Active session: fetch equity then scan each pair ──────────────
            try:
                account_info = await client.get_account_info()
                equity = account_info.equity
            except Exception as e:
                logger.warning("Could not fetch account info: %s", e)
                await asyncio.sleep(POLL_INTERVAL)
                continue

            logger.info(
                "[%s] equity=%.2f balance=%.2f  %s",
                session.upper(),
                equity,
                account_info.balance,
                risk.summary(),
            )

            for symbol in PAIRS:
                try:
                    await _scan_pair(
                        symbol=symbol,
                        equity=equity,
                        client=client,
                        order_manager=order_manager,
                        telegram=telegram,
                        trade_logger=trade_logger,
                        seen=seen_signals[symbol],
                    )
                except Exception as e:
                    logger.exception("Error scanning %s: %s", symbol, e)
                    trade_logger.error(symbol, str(e), "scan_pair")
                    await telegram.send_error(f"{symbol}: {e}")

            await asyncio.sleep(POLL_INTERVAL)

    except KeyboardInterrupt:
        logger.info("Shutdown requested")
    except Exception as e:
        logger.exception("Fatal error: %s", e)
        trade_logger.error("BOT", str(e), "fatal")
        await telegram.send_error(f"Fatal: {e}")
    finally:
        watchdog_task.cancel()
        try:
            await watchdog_task
        except asyncio.CancelledError:
            pass
        await client.disconnect()
        await telegram.stop()
        logger.info("Bot stopped")


# ── Pair scanner ──────────────────────────────────────────────────────────────


async def _scan_pair(
    symbol: str,
    equity: float,
    client: MetaAPIClient,
    order_manager: OrderManager,
    telegram: TelegramAlerter,
    trade_logger: TradeLogger,
    seen: set,
) -> None:
    """
    Fetch latest candles, run ST-A2 strategy, process any new signals.

    Dedup by signal.timestamp.isoformat() so the same signal is never submitted
    twice across multiple polls within the same 15-minute bar.
    """
    m15 = await client.get_candles(symbol, "15m", count=300)
    h4 = await client.get_candles(symbol, "4h", count=200)

    if len(m15) < 20:
        logger.debug("[%s] Insufficient M15 candles (%d) — skipping", symbol, len(m15))
        return

    signals = run_strategy(m15, h4, symbol)

    for sig in signals:
        key = sig.timestamp.isoformat()
        if key in seen:
            continue
        seen.add(key)

        logger.info(
            "[%s] New signal: %s %s  entry=%.5f sl=%.5f  ts=%s",
            symbol,
            sig.side.upper(),
            sig.session,
            sig.entry,
            sig.stop_loss,
            key,
        )

        success, detail = await order_manager.process_signal(sig, symbol, equity)

        if success:
            global _LAST_SIGNAL_TIME
            _LAST_SIGNAL_TIME = datetime.now(timezone.utc)
            await telegram.send_trade_open(
                symbol=symbol,
                direction=sig.side,
                entry=sig.entry,
                sl=sig.stop_loss,
                tp=sig.take_profit,
                risk_pct=CONFIG["risk"]["risk_per_trade_pct"],
                lot=0.0,  # actual lot in trade_logger; telegram shows signal price
                dry_run=not LIVE_TRADING,
            )
        else:
            logger.info("[%s] Signal not actioned: %s", symbol, detail)


# ── Session-end position close ────────────────────────────────────────────────


async def _close_session_positions(
    client: MetaAPIClient,
    telegram: TelegramAlerter,
    session: str,
    config: dict,
) -> None:
    """Close all bot-managed positions still open at session end."""
    magic_numbers = list(config.get("magic_numbers", {}).values())
    positions = await client.get_open_positions()
    bot_positions = [p for p in positions if p.magic in magic_numbers]

    closed = 0
    for pos in bot_positions:
        ok = await client.close_position(pos.position_id)
        if ok:
            closed += 1
            logger.info(
                "Session-end close: %s %s id=%s",
                pos.direction,
                pos.symbol,
                pos.position_id,
            )

    await telegram.send_session_close(session, closed)


# ── Health monitor ────────────────────────────────────────────────────────────


async def _send_heartbeat(
    client: MetaAPIClient,
    telegram: TelegramAlerter,
    now: datetime,
) -> None:
    """Log and send 5-minute heartbeat with full OPS-01 fields.

    Never blocks indefinitely: all RPC calls are bounded by RPC_TIMEOUT_S (30s)
    inside MetaAPIClient._rpc(). asyncio.TimeoutError is caught here to log
    ERROR and schedule a reconnect attempt without aborting the heartbeat loop.
    """
    global _last_heartbeat_ts
    status = client.connection_status()
    uptime_s = int((now - _BOT_START_TIME).total_seconds())
    last_sig = _LAST_SIGNAL_TIME.strftime("%H:%MZ") if _LAST_SIGNAL_TIME else "none"
    connection_status = "CONNECTED" if status["connected"] else "DISCONNECTED"

    try:
        info = await client.get_account_info()
        balance = info.balance
        equity = info.equity
        positions = await client.get_open_positions()
        n_pos = len(positions)
    except asyncio.TimeoutError:
        balance = 0.0
        equity = 0.0
        n_pos = -1
        connection_status = "DISCONNECTED"
        logger.error(
            "[HEARTBEAT] RPC timeout — MetaAPI unavailable, reconnect will be attempted"
        )
    except Exception:
        balance = 0.0
        equity = 0.0
        n_pos = -1

    msg = (
        f"[HEARTBEAT] {now.strftime('%Y-%m-%dT%H:%M UTC')}\n"
        f"uptime={uptime_s}s  connection_status={connection_status}  live={status['live_trading']}\n"
        f"balance={balance:.2f}  equity={equity:.2f}  open_positions={n_pos}\n"
        f"last_signal={last_sig}"
    )
    logger.info(msg)
    _last_heartbeat_ts = now  # watchdog reads this to confirm heartbeat fired
    await telegram.send(msg)


# ── Watchdog ──────────────────────────────────────────────────────────────────


async def _run_watchdog(telegram: TelegramAlerter) -> None:
    """Fire a CRITICAL alert if no heartbeat has been logged for WATCHDOG_TIMEOUT_S.

    Runs as an independent asyncio Task so it remains alive even when the main
    coroutine is sleeping or blocked. Checks once per minute.
    """
    while True:
        await asyncio.sleep(60)
        age = (datetime.now(timezone.utc) - _last_heartbeat_ts).total_seconds()
        if age >= WATCHDOG_TIMEOUT_S:
            logger.critical(
                "WATCHDOG: No heartbeat for %.0fs (threshold=%ds) — bot may be hung",
                age,
                WATCHDOG_TIMEOUT_S,
            )
            await telegram.send(
                f"[CRITICAL] No heartbeat for {age:.0f}s "
                f"(threshold={WATCHDOG_TIMEOUT_S}s) — bot may be hung"
            )


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    asyncio.run(run_bot())
