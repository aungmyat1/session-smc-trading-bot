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

from monitoring.logging_utils import build_gzip_timed_rotating_handler
from approval_package.package_validator import validate_package

load_dotenv()

# ── Logging ──────────────────────────────────────────────────────────────────

Path("logs").mkdir(exist_ok=True)

_file_handler = build_gzip_timed_rotating_handler(
    "logs/bot.log",
    backup_count=7,
)

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
BROKER_MODE: str = os.getenv("BROKER_MODE", "metaapi").lower().strip()

METAAPI_TOKEN: str = os.getenv("METAAPI_TOKEN", "")
METAAPI_ACCOUNT_ID: str = os.getenv("METAAPI_ACCOUNT_ID", "")
TELEGRAM_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")

HEARTBEAT_INTERVAL_S: int = 300   # 5 minutes
WATCHDOG_TIMEOUT_S: int = 600     # 10 minutes — CRITICAL alert if no heartbeat fires
_RECONNECT_BACKOFF_S: int = 120   # try reconnect every 2 min when disconnected
_last_reconnect_attempt: "datetime | None" = None
_BOT_START_TIME: datetime = datetime.now(timezone.utc)
_LAST_SIGNAL_TIME: "datetime | None" = None
_last_heartbeat_ts: datetime = datetime.now(timezone.utc)  # updated each time heartbeat logs
_CONNECT_RETRY_MAX: int = 12
_CONNECT_RETRY_BASE_S: int = 5

# ── Imports ───────────────────────────────────────────────────────────────────

from data.session_filter import get_active_session, seconds_to_next_session
from core.broker_interface import BrokerInterface
from execution.metaapi_client import MetaAPIClient
from execution.order_manager import OrderManager
from execution.risk_manager import RiskManager
from execution.trade_logger import TradeLogger
from execution_simulator.broker.virtual_broker import VirtualBroker
from monitoring.telegram import TelegramAlerter
from strategy.session_liquidity.session_strategy import run_strategy

# ADR-0003: compatibility implementation only. Runtime lifecycle ownership
# belongs to production.engine.RuntimeAuthority.
LEGACY_RUNTIME_ENTRYPOINT = True


# ── Broker wiring ───────────────────────────────────────────────────────────

def _build_recovery_summary(
    trade_logger: TradeLogger,
    risk: RiskManager,
    seen_signals: dict[str, set[str]],
) -> str:
    """Summarize restart-recovered bot state for startup alerting."""
    counts = {
        "signals": 0,
        "orders": 0,
        "fills": 0,
        "rejections": 0,
        "closes": 0,
        "errors": 0,
    }
    for event in trade_logger.iter_events():
        match event.get("event"):
            case "SIGNAL_CREATED":
                counts["signals"] += 1
            case "ORDER_SUBMITTED":
                counts["orders"] += 1
            case "ORDER_FILLED":
                counts["fills"] += 1
            case "ORDER_REJECTED":
                counts["rejections"] += 1
            case "POSITION_CLOSED":
                counts["closes"] += 1
            case "ERROR":
                counts["errors"] += 1
    seen_total = sum(len(v) for v in seen_signals.values())
    state = risk.state
    lines = [
        f"- recovered_signals={seen_total}",
        f"- journal: signals={counts['signals']} orders={counts['orders']} fills={counts['fills']} closes={counts['closes']} errors={counts['errors']}",
        f"- risk_state: daily_loss={state.daily_loss_r:.2f}R weekly_loss={state.weekly_loss_r:.2f}R consec_losses={state.consecutive_losses}",
        f"- halt_state: halted={state.halted} reason={state.halt_reason or 'none'}",
    ]
    return "\n".join(lines)

def _build_execution_client(
    market_client: MetaAPIClient | None = None,
    broker: BrokerInterface | None = None,
) -> BrokerInterface | MetaAPIClient:
    """
    Return the order-execution backend.

    Default behavior keeps the existing MetaAPI path. When a broker instance is
    injected, the bot can send orders through the virtual broker without the
    strategy knowing the difference.
    """
    if broker is not None:
        return broker
    if BROKER_MODE == "virtual":
        return VirtualBroker()
    if market_client is None:
        return MetaAPIClient(METAAPI_TOKEN, METAAPI_ACCOUNT_ID)
    return market_client


# ── Main loop ─────────────────────────────────────────────────────────────────

async def run_bot(
    market_client: MetaAPIClient | None = None,
    broker: BrokerInterface | None = None,
    approved_package_path: str | Path | None = None,
) -> None:
    package_path = approved_package_path or os.getenv("APPROVED_STRATEGY_PACKAGE", "")
    package_result = validate_package(package_path) if package_path else None
    if package_result is None:
        logger.error("Bot startup rejected: APPROVED_STRATEGY_PACKAGE is not configured")
        raise PermissionError("bot requires an approved strategy package")
    if not package_result.valid:
        logger.error("Bot startup rejected: %s", "; ".join(package_result.reasons))
        package_result.require_valid()
    logger.info("Approved strategy package accepted: %s", package_result.package_path)
    telegram = TelegramAlerter(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)
    await telegram.start()

    client = market_client or MetaAPIClient(METAAPI_TOKEN, METAAPI_ACCOUNT_ID)
    execution_client = _build_execution_client(market_client=client, broker=broker)
    risk = RiskManager(CONFIG)
    trade_logger = TradeLogger()
    order_manager = OrderManager(execution_client, risk, trade_logger, CONFIG)

    # Dedup: track signal timestamps already processed, per symbol
    global _BOT_START_TIME, _LAST_SIGNAL_TIME, _last_heartbeat_ts, _last_reconnect_attempt
    _BOT_START_TIME = datetime.now(timezone.utc)
    _last_heartbeat_ts = _BOT_START_TIME

    seen_signals: dict[str, set[str]] = _load_seen_signals(trade_logger, PAIRS)

    last_session: "str | None" = None
    last_heartbeat: datetime = datetime.now(timezone.utc)
    # SAFETY-01: last-known-open broker positions, keyed by position_id.
    # Diffed each loop tick to detect closes and feed real trade results into
    # RiskManager.record_trade_result() — see _process_closed_positions().
    last_positions: dict[str, object] = {}

    watchdog_task = asyncio.create_task(_run_watchdog(telegram))

    try:
        if isinstance(execution_client, MetaAPIClient):
            logger.info("Connecting to MetaAPI (LIVE_TRADING=%s)…", LIVE_TRADING)
            await _connect_with_retry(execution_client, telegram)
            logger.info("MetaAPI connected.")
        else:
            logger.info("Using execution broker: %s", execution_client.__class__.__name__)
            await execution_client.connect()

        recovery_summary = _build_recovery_summary(trade_logger, risk, seen_signals)
        await telegram.send_startup(
            PAIRS,
            CONFIG["risk"]["risk_per_trade_pct"],
            LIVE_TRADING,
            recovery_summary=recovery_summary,
        )

        while True:
            now = datetime.now(timezone.utc)
            session = get_active_session(now)

            # ── Heartbeat (every 5 min) ───────────────────────────────────────
            elapsed = (now - last_heartbeat).total_seconds()
            if elapsed >= HEARTBEAT_INTERVAL_S:
                await _send_heartbeat(execution_client, telegram, now)
                last_heartbeat = now
                if isinstance(execution_client, MetaAPIClient) and not execution_client.is_connected:
                    if session:
                        logger.info("Connection lost after heartbeat — attempting reconnect")
                        if await execution_client.reconnect():
                            _last_reconnect_attempt = None
                            await telegram.send_reconnect_success("MetaAPI")
                        else:
                            logger.info(
                                "Connection lost after heartbeat during off-hours — reconnect deferred until session opens"
                            )

            # ── Session boundary ──────────────────────────────────────────────
            if session != last_session:
                if last_session is not None:
                    await _close_session_positions(execution_client, telegram, last_session, CONFIG)
                if session:
                    await telegram.send_session_open(session)
                last_session = session

            # ── Closed-position reconciliation (SAFETY-01) ────────────────────
            # Runs every tick, independent of halt/session state, so real
            # trade outcomes always reach the risk engine's loss counters.
            last_positions = await _process_closed_positions(
                execution_client, risk, trade_logger, telegram, CONFIG, last_positions,
            )

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

            # ── Reconnect if disconnected (every 2 min, not just at heartbeat) ─
            if isinstance(execution_client, MetaAPIClient) and not execution_client.is_connected:
                now2 = datetime.now(timezone.utc)
                since = (now2 - _last_reconnect_attempt).total_seconds() if _last_reconnect_attempt else 999
                if since >= _RECONNECT_BACKOFF_S:
                    logger.info("Disconnected — attempting reconnect")
                    _last_reconnect_attempt = now2
                    ok = await execution_client.reconnect()
                    if ok:
                        _last_reconnect_attempt = None
                        await telegram.send_reconnect_success("MetaAPI")
                    else:
                        await telegram.send_reconnect_failure("MetaAPI", "during active session")
                        await telegram.send_error("MetaAPI reconnect failed during active session")
                        await asyncio.sleep(POLL_INTERVAL)
                        continue
                else:
                    await asyncio.sleep(POLL_INTERVAL)
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
                session.upper(), equity, account_info.balance, risk.summary(),
            )

            for symbol in PAIRS:
                try:
                    await _scan_pair(
                        symbol=symbol,
                        equity=equity,
                        market_client=client,
                        execution_client=execution_client,
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
        await execution_client.disconnect()
    await telegram.stop()
    logger.info("Bot stopped")


async def _connect_with_retry(client: MetaAPIClient, telegram: TelegramAlerter) -> None:
    """Keep retrying initial MetaAPI connect through transient websocket failures."""
    delay_s = _CONNECT_RETRY_BASE_S
    for attempt in range(1, _CONNECT_RETRY_MAX + 1):
        try:
            await client.connect()
            return
        except Exception as exc:
            logger.warning(
                "MetaAPI connect attempt %d/%d failed: %s",
                attempt, _CONNECT_RETRY_MAX, exc,
            )
            if attempt >= _CONNECT_RETRY_MAX:
                raise
            await telegram.send_error(
                f"MetaAPI connect attempt {attempt} failed: {exc}"
            )
            await asyncio.sleep(delay_s)
            delay_s = min(delay_s * 2, 60)


# ── Pair scanner ──────────────────────────────────────────────────────────────

async def _scan_pair(
    symbol: str,
    equity: float,
    market_client: MetaAPIClient,
    execution_client: BrokerInterface | MetaAPIClient,
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
    m15 = await market_client.get_candles(symbol, "15m", count=300)
    h4 = await market_client.get_candles(symbol, "4h", count=200)

    if len(m15) < 20:
        logger.debug("[%s] Insufficient M15 candles (%d) — skipping", symbol, len(m15))
        return

    signals = run_strategy(
        m15,
        h4,
        symbol,
        config=CONFIG.get("session_strategy", {}),
    )

    for sig in signals:
        key = sig.timestamp.isoformat()
        if key in seen:
            continue
        seen.add(key)

        logger.info(
            "[%s] New signal: %s %s  entry=%.5f sl=%.5f  ts=%s",
            symbol, sig.side.upper(), sig.session, sig.entry, sig.stop_loss, key,
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
                lot=0.0,       # actual lot in trade_logger; telegram shows signal price
                dry_run=not LIVE_TRADING,
            )
        else:
            logger.info("[%s] Signal not actioned: %s", symbol, detail)


def _load_seen_signals(trade_logger: TradeLogger, pairs: list[str]) -> dict[str, set[str]]:
    """Rebuild per-symbol signal dedup state from the append-only trade log."""
    seen: dict[str, set[str]] = {sym: set() for sym in pairs}
    for event in trade_logger.iter_events():
        if event.get("event") != "SIGNAL_CREATED":
            continue
        symbol = event.get("symbol")
        signal_ts = event.get("signal_ts")
        if symbol in seen and signal_ts:
            seen[symbol].add(str(signal_ts))
    return seen


# ── Closed-position reconciliation (SAFETY-01) ─────────────────────────────────

# Pip size per symbol, needed to convert a raw price distance (open_price -
# sl) into pips for R-multiple math. Mirrors the same _PIP convention already
# duplicated across strategies/adapters/*.py and session_smc/*.py — not
# consolidated here to stay within this task's file-count scope.
_PIP_SIZE: dict[str, float] = {"EURUSD": 0.0001, "GBPUSD": 0.0001, "USDJPY": 0.01, "XAUUSD": 0.1}


async def _process_closed_positions(
    execution_client: "BrokerInterface | MetaAPIClient",
    risk: RiskManager,
    trade_logger: TradeLogger,
    telegram: TelegramAlerter,
    config: dict,
    last_positions: dict[str, object],
) -> dict[str, object]:
    """Detect broker positions that closed since the previous poll and feed
    their realized R-multiple into RiskManager.record_trade_result().

    Without this, daily/weekly/monthly loss and consecutive-loss circuit
    breakers never update from real closes (record_trade_result had zero
    live call sites — see docs/VERDICT_LOG.md SAFETY-01).

    Diff-based on position_id, mirroring execution/close_reconciliation.py's
    approach for the demo-runner path. Known limitation: MetaAPIClient has no
    get_closing_deal()-equivalent lookup, so the profit/close price used here
    is the last-known open snapshot before the position disappeared, not a
    guaranteed final broker deal record. R-multiple is derived from the
    position's own open_price/sl/volume (risk_amount = |open-sl| pips ×
    pip_value × lots), so it does not depend on any separate journal store.
    """
    try:
        current = await execution_client.get_open_positions()
    except Exception as e:
        logger.warning("Could not fetch positions for close reconciliation: %s", e)
        return last_positions

    current_by_id = {p.position_id: p for p in current if getattr(p, "position_id", "")}
    closed_ids = [pid for pid in last_positions if pid not in current_by_id]

    pip_value_per_lot: dict = config.get("pip_value_per_lot", {})
    was_halted = risk.state.halted

    for pid in closed_ids:
        pos = last_positions[pid]
        pip_size = _PIP_SIZE.get(pos.symbol, 0.0001)
        risk_pips = abs(pos.open_price - pos.sl) / pip_size if pos.sl else 0.0
        pv = pip_value_per_lot.get(pos.symbol, 10.0)
        risk_amount = risk_pips * pv * pos.volume
        result_r = (pos.profit / risk_amount) if risk_amount > 0 else 0.0

        risk.record_trade_result(result_r)
        trade_logger.position_closed(pos.symbol, pid, result_r, "broker_position_closed")
        logger.info(
            "Position closed: %s %s profit=%.2f result_r=%.3fR halted=%s",
            pos.symbol, pid, pos.profit, result_r, risk.state.halted,
        )
        await telegram.send_trade_close(
            symbol=pos.symbol,
            direction=pos.direction,
            result_r=result_r,
            reason="broker_position_closed",
        )

    # Fail-safe: alert the moment a circuit breaker actually trips (not just
    # on the next pre-trade check), so a halt is never silent.
    if risk.state.halted and not was_halted:
        logger.critical(
            "CIRCUIT BREAKER TRIPPED: %s — new entries halted. %s",
            risk.state.halt_reason, risk.summary(),
        )
        await telegram.send_circuit_breaker(risk.state.halt_reason, risk.summary())

    return current_by_id


# ── Session-end position close ────────────────────────────────────────────────

async def _close_session_positions(
    client: BrokerInterface | MetaAPIClient,
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
                pos.direction, pos.symbol, pos.position_id,
            )

    await telegram.send_session_close(session, closed)


# ── Health monitor ────────────────────────────────────────────────────────────

async def _send_heartbeat(
    client: BrokerInterface | MetaAPIClient,
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
    _last_heartbeat_ts = now   # watchdog reads this to confirm heartbeat fired
    await telegram.send_heartbeat(
        timestamp_label=now.strftime('%Y-%m-%dT%H:%M UTC'),
        uptime_s=uptime_s,
        connection_status=connection_status,
        live_trading=status["live_trading"],
        balance=balance,
        equity=equity,
        open_positions=n_pos,
        last_signal=last_sig,
    )


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
                age, WATCHDOG_TIMEOUT_S,
            )
            await telegram.send_watchdog_critical(
                age_s=age,
                threshold_s=WATCHDOG_TIMEOUT_S,
            )


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    asyncio.run(run_bot())
