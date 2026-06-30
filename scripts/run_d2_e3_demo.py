#!/usr/bin/env python3
"""D2 E3 Demo Runner — Vantage MT5 demo account via MetaAPI.

Strategy: ST-D2-E3-OPT2 — PDH/PDL sweep + 12-bar MSS + 50% limit entry
Session:  08:00–16:00 UTC  |  EURUSD + GBPUSD  |  Risk 0.5%

Env vars (from .env):
    VANTAGE_DEMO_METAAPI_ID  — MetaAPI account ID for Vantage demo
    METAAPI_TOKEN            — MetaAPI API token
    TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID
    DEMO_LIVE=false          — set 'true' to send orders to Vantage demo MT5
                               (false = dry-run: signals logged, no orders sent)
    LIVE_TRADING             — must remain false (real-money guard; owner sets only)

Run:
    python3 scripts/run_d2_e3_demo.py
"""
from __future__ import annotations

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

load_dotenv()

# ── Logging ───────────────────────────────────────────────────────────────────

Path("logs").mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        build_gzip_timed_rotating_handler(
            "logs/d2e3_demo.log",
            backup_count=7,
        ),
    ],
)
log = logging.getLogger("d2e3")

# ── Config ────────────────────────────────────────────────────────────────────

METAAPI_TOKEN = os.getenv("METAAPI_TOKEN", "")
ACCOUNT_ID    = os.getenv("VANTAGE_DEMO_METAAPI_ID", "")
TG_TOKEN      = os.getenv("TELEGRAM_BOT_TOKEN", "")
TG_CHAT       = os.getenv("TELEGRAM_CHAT_ID", "")

# DEMO_LIVE=true  → orders sent to Vantage demo MT5 (paper money)
# DEMO_LIVE=false → dry-run only (no MetaAPI order calls)
DEMO_LIVE    = os.getenv("DEMO_LIVE", "false").lower() == "true"
LIVE_TRADING = os.getenv("LIVE_TRADING", "false").lower() == "true"

SYMBOLS       = ["EURUSD", "GBPUSD"]
MAGIC         = {"EURUSD": 31001, "GBPUSD": 31002}  # distinct from ST-A2 (21001/21002)
RISK_PCT      = 0.005   # 0.5% per trade
PIP_VALUE     = {"EURUSD": 10.0, "GBPUSD": 10.0}   # USD/pip at 1.0 lot
PIP           = {"EURUSD": 0.0001, "GBPUSD": 0.0001}
MIN_LOT       = 0.01
POLL_INTERVAL = 60      # seconds

sys.path.insert(0, str(Path(__file__).parent.parent))
from execution.metaapi_client import MetaAPIClient
from execution.trade_logger import TradeLogger
from strategy.d2_e3.signal_engine import D2E3Engine, D2E3Params


# ── Helpers ───────────────────────────────────────────────────────────────────

def _lot(balance: float, stop_pips: float, symbol: str) -> float:
    risk_usd = balance * RISK_PCT
    raw = risk_usd / (stop_pips * PIP_VALUE[symbol])
    return max(MIN_LOT, round(raw / MIN_LOT) * MIN_LOT)


async def _tg(msg: str) -> None:
    if not TG_TOKEN or not TG_CHAT:
        return
    try:
        import aiohttp
        async with aiohttp.ClientSession() as s:
            await s.post(
                f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
                json={"chat_id": TG_CHAT, "text": msg},
                timeout=aiohttp.ClientTimeout(total=5),
            )
    except Exception as e:
        log.warning("Telegram: %s", e)


def _in_session(now: datetime) -> bool:
    return 8 <= now.hour < 16


async def _connect_with_retry(client: MetaAPIClient, *, label: str) -> None:
    """Retry initial MetaAPI connect so transient websocket timeouts don't abort the bot."""
    delay_s = 5
    for attempt in range(1, 13):
        try:
            await client.connect()
            return
        except Exception as exc:
            log.warning("%s connect attempt %d/12 failed: %s", label, attempt, exc)
            if attempt >= 12:
                raise
            await _tg(f"[{label}] connect attempt {attempt} failed: {exc}")
            await asyncio.sleep(delay_s)
            delay_s = min(delay_s * 2, 60)


def _holdout_passed() -> tuple[bool, str]:
    """Allow DEMO_LIVE only when the locked holdout result is a PASS."""
    result_path = Path("backtest_output_d2_holdout/holdout_result.json")
    if not result_path.exists():
        return False, f"missing holdout result: {result_path}"
    try:
        result = json.loads(result_path.read_text())
    except Exception as exc:
        return False, f"could not parse holdout result: {exc}"
    if result.get("trial") != "ST-D2-E3-OPT2":
        return False, f"unexpected holdout trial: {result.get('trial')}"
    gate = result.get("gate", {})
    if not gate.get("PASS", False):
        return False, "holdout gate did not PASS"
    return True, "holdout gate passed"


# ── Per-symbol state ──────────────────────────────────────────────────────────

class _SymState:
    def __init__(self):
        self.active_limit_id: str | None = None   # MetaAPI pending order ID
        self.open_position_id: str | None = None  # MetaAPI position ID
        self.pending_lot: float = 0.0
        self.pending_entry: float = 0.0
        self.pending_stop: float = 0.0
        self.pending_target: float = 0.0
        self.pending_equity: float = 0.0
        self.pending_reason: str = ""
        self.pending_signal_ts: str = ""


def _session_label() -> str:
    return "utc"


def _log_signal(logger: TradeLogger, sym: str, sig, *, reason: str) -> None:
    stop_pips = abs(sig.entry - sig.stop) / PIP[sym] if sig.entry and sig.stop else 0.0
    logger.signal_created(
        symbol=sym,
        session=_session_label(),
        side=sig.direction,
        entry=float(sig.entry or 0.0),
        sl=float(sig.stop or 0.0),
        tp=float(sig.target or 0.0),
        sl_pips=round(stop_pips, 2),
        reason=reason,
        signal_ts=sig.bar_time or None,
    )


def _log_submission(
    logger: TradeLogger,
    sym: str,
    *,
    direction: str,
    lot: float,
    stop: float,
    target: float,
    equity: float,
) -> None:
    logger.order_submitted(
        symbol=sym,
        session=_session_label(),
        direction=direction,
        volume=lot,
        sl=stop,
        tp=target,
        lots=lot,
        equity=equity,
        risk_pct=RISK_PCT * 100.0,
        dry_run=not DEMO_LIVE,
    )


def _log_fill(
    logger: TradeLogger,
    sym: str,
    *,
    order_id: str,
    entry: float,
    lot: float,
    stop: float,
    target: float,
    dry_run: bool,
) -> None:
    logger.order_filled(
        symbol=sym,
        order_id=order_id,
        entry_price=entry,
        volume=lot,
        sl=stop,
        tp=target,
        dry_run=dry_run,
    )


# ── Main loop ─────────────────────────────────────────────────────────────────

async def run() -> None:
    if LIVE_TRADING:
        log.error("LIVE_TRADING=true — this script is demo-only. Abort.")
        return
    if not ACCOUNT_ID:
        log.error("VANTAGE_DEMO_METAAPI_ID not set in .env")
        return
    if DEMO_LIVE:
        ok, reason = _holdout_passed()
        if not ok:
            log.error("DEMO_LIVE blocked: %s", reason)
            await _tg(f"[D2E3-DEMO] DEMO_LIVE blocked: {reason}")
            return

    log.info("D2E3 demo starting (DEMO_LIVE=%s, account=…%s)", DEMO_LIVE, ACCOUNT_ID[-6:])
    await _tg(f"[D2E3-DEMO] Started DEMO_LIVE={DEMO_LIVE}  pairs={SYMBOLS}  risk={RISK_PCT*100}%")

    client = MetaAPIClient(METAAPI_TOKEN, ACCOUNT_ID)
    trade_logger = TradeLogger(Path("logs") / "d2e3_trades.jsonl")
    params = D2E3Params()
    engines = {sym: D2E3Engine(sym, params) for sym in SYMBOLS}
    sym_state = {sym: _SymState() for sym in SYMBOLS}

    try:
        await _connect_with_retry(client, label="D2E3")
        log.info("Connected to Vantage demo")

        while True:
            now = datetime.now(timezone.utc)

            if not _in_session(now):
                secs_to_open = ((8 - now.hour) % 24) * 3600 - now.minute * 60 - now.second
                log.info("Off-session. Next open in %ds", secs_to_open)
                await asyncio.sleep(min(max(secs_to_open, 60), 1800))
                continue

            try:
                info = await client.get_account_info()
                balance = info.balance
            except Exception as e:
                log.warning("Account info error: %s", e)
                await asyncio.sleep(POLL_INTERVAL)
                continue

            for sym in SYMBOLS:
                try:
                    await _scan(sym, balance, client, engines[sym], sym_state[sym], trade_logger)
                except Exception as e:
                    log.exception("[%s] error: %s", sym, e)

            await asyncio.sleep(POLL_INTERVAL)

    except KeyboardInterrupt:
        log.info("Shutdown requested")
    finally:
        await client.disconnect()
        await _tg("[D2E3-DEMO] Bot stopped")


# ── Per-symbol scan ───────────────────────────────────────────────────────────

async def _scan(
    sym: str,
    balance: float,
    client: MetaAPIClient,
    engine: D2E3Engine,
    state: _SymState,
    trade_logger: TradeLogger,
) -> None:
    bars = await client.get_candles(sym, "15m", count=350)
    if len(bars) < 50:
        return

    signals = engine.process_bars(bars)
    for sig in signals:
        log.info("[%s] %s dir=%s entry=%.5f stop=%.5f tgt=%.5f r=%+.2f %s",
                 sym, sig.type, sig.direction, sig.entry, sig.stop,
                 sig.target, sig.r, sig.exit_reason or sig.detail)

        if sig.type == "setup_detected":
            _log_signal(trade_logger, sym, sig, reason=sig.detail or sig.type)
            await _tg(f"[D2E3] {sym} {sig.direction.upper()} setup — {sig.detail}")

        elif sig.type == "mss_confirmed":
            stop_pips = abs(sig.entry - sig.stop) / PIP[sym]
            lot = _lot(balance, stop_pips, sym)
            side = "buy" if sig.direction == "long" else "sell"
            state.pending_lot = lot
            state.pending_entry = sig.entry
            state.pending_stop = sig.stop
            state.pending_target = sig.target
            state.pending_equity = balance
            state.pending_reason = sig.detail or sig.type
            state.pending_signal_ts = sig.bar_time

            _log_submission(
                trade_logger,
                sym,
                direction=sig.direction,
                lot=lot,
                stop=sig.stop,
                target=sig.target,
                equity=balance,
            )

            if DEMO_LIVE and not state.active_limit_id:
                try:
                    res = await client.place_limit_order(
                        symbol=sym, direction=sig.direction,
                        volume=lot, price=sig.entry,
                        sl=sig.stop, tp=sig.target,
                        magic=MAGIC[sym], comment="D2E3-demo",
                    )
                    state.active_limit_id = res.order_id
                except Exception as e:
                    log.error("[%s] place_limit_order failed: %s", sym, e)
                    trade_logger.order_rejected(sym, f"ORDER_FAILED:{e}", sig.direction)
                    await _tg(f"[D2E3] {sym} limit order ERROR: {e}")
            else:
                log.info("[%s] DRY-RUN limit %s @ %.5f  SL=%.5f  TP=%.5f  lot=%.2f",
                         sym, side.upper(), sig.entry, sig.stop, sig.target, lot)

            await _tg(
                f"[D2E3{'|DEMO_LIVE' if DEMO_LIVE else '|DRY-RUN'}] "
                f"{sym} {side.upper()} limit @ {sig.entry:.5f}  "
                f"SL={sig.stop:.5f}  TP={sig.target:.5f}  lot={lot:.2f}"
            )

        elif sig.type == "entry_filled":
            order_id = state.active_limit_id or state.open_position_id or f"{sym}:{sig.bar_time}"
            _log_fill(
                trade_logger,
                sym,
                order_id=order_id,
                entry=sig.entry,
                lot=state.pending_lot or _lot(balance, abs(sig.entry - sig.stop) / PIP[sym], sym),
                stop=sig.stop,
                target=sig.target,
                dry_run=not DEMO_LIVE,
            )
            await _tg(
                f"[D2E3] {sym} {sig.direction.upper()} FILLED @ {sig.entry:.5f}  "
                f"SL={sig.stop:.5f}  TP={sig.target:.5f}"
            )
            state.active_limit_id = None
            # Look up actual position for time-based close later
            if DEMO_LIVE:
                positions = await client.get_open_positions(magic=MAGIC[sym])
                for p in positions:
                    if p.symbol == sym:
                        state.open_position_id = p.position_id
                        break

        elif sig.type == "setup_expired":
            if state.active_limit_id and DEMO_LIVE:
                await client.cancel_order(state.active_limit_id)
            trade_logger.order_rejected(sym, "SETUP_EXPIRED", sig.direction)
            state.active_limit_id = None
            log.info("[%s] Setup expired — limit cancelled", sym)

        elif sig.type == "trade_closed":
            trade_logger.position_closed(
                sym,
                state.open_position_id or f"{sym}:{sig.bar_time}",
                sig.r,
                sig.exit_reason,
            )
            emoji = "✅" if sig.r > 0 else "❌"
            await _tg(
                f"[D2E3] {sym} {sig.direction.upper()} CLOSED {emoji}  "
                f"{sig.exit_reason}  R={sig.r:+.2f}"
            )
            # TIME exits need explicit close (SL/TP handled by broker)
            if sig.exit_reason == "TIME" and state.open_position_id and DEMO_LIVE:
                await client.close_position(state.open_position_id)
            state.open_position_id = None
            state.active_limit_id = None
            state.pending_lot = 0.0
            state.pending_entry = 0.0
            state.pending_stop = 0.0
            state.pending_target = 0.0
            state.pending_equity = 0.0
            state.pending_reason = ""
            state.pending_signal_ts = ""


if __name__ == "__main__":
    asyncio.run(run())
