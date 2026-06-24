"""
ST-A2 Demo Runner — shadow/paper execution on Vantage MT5 demo.

Flow per tick:
  MarketData → ST-A2 Signal → Spread Check → Risk Check → TradeManager → Journal

DRY_RUN=true (default): all order logic runs but no order is placed.
DEMO_ONLY=true (default): gated at executor level even if DRY_RUN=false.

Usage:
    python3 scripts/run_st_a2_demo.py
    python3 scripts/run_st_a2_demo.py --interval 60 --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(_ROOT / ".env")
except ImportError:
    pass

# ── Strategy plugin layer ─────────────────────────────────────────────────────
from core.strategy_registry import register_strategy, get_strategy
from strategies.adapters.st_a2_adapter import ST2Adapter

_st2 = ST2Adapter()
register_strategy(_st2)

# ── Demo execution stack ──────────────────────────────────────────────────────
from execution.mt5_connector      import MT5Connector
from execution.vantage_demo_executor import VantageDemoExecutor
from execution.trade_manager       import TradeManager
from execution.demo_risk_manager   import (
    calculate_lots, new_state, check_limits, record_result, reset_daily,
)
from execution.trade_journal       import DemoTradeJournal

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(Path("logs") / "st_a2_demo.log"),
    ],
)
# Suppress SDK noise — keep only WARNING+ from transport layers
for _noisy in ("engineio", "socketio", "engineio.client", "socketio.client", "httpx"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)
_log = logging.getLogger("st_a2.runner")

PAIRS    = ["EURUSD", "GBPUSD"]
INTERVAL = 60   # seconds
MAX_SPREAD_PIPS: dict[str, float] = {"EURUSD": 1.5, "GBPUSD": 2.0}


async def _tick(
    executor:  VantageDemoExecutor,
    manager:   TradeManager,
    journal:   DemoTradeJournal,
    risk_state: dict,
    dry_run:   bool,
) -> dict:
    """One scan cycle. Returns updated risk_state."""

    # Daily reset
    from datetime import date
    today = date.today().isoformat()
    if risk_state.get("last_reset", "")[:10] != today:
        risk_state = reset_daily(risk_state)
        _log.info("Daily risk state reset.")

    for symbol in PAIRS:
        # ── Check risk limits before fetching data ───────────────────────
        limit = check_limits(risk_state)
        if not limit["approved"]:
            _log.info("SKIP %s — %s", symbol, limit["reason"])
            continue

        # ── Fetch candles ────────────────────────────────────────────────
        try:
            m15 = await executor.get_candles(symbol, "M15", 200)
            h4  = await executor.get_candles(symbol, "H4",  100)
            px  = await executor.get_price(symbol)
        except Exception as exc:
            _log.warning("Data fetch error %s: %s", symbol, exc)
            continue

        spread = px["spread_pips"]
        max_sp = MAX_SPREAD_PIPS.get(symbol, 2.0)
        if spread > max_sp:
            _log.info("SKIP %s — spread %.1f > %.1f", symbol, spread, max_sp)
            continue

        if len(m15) < 50:
            _log.debug("Insufficient bars %s", symbol)
            continue

        _log.info("TICK %s  bars=%d  spread=%.1fpip  price=%.5f",
                  symbol, len(m15), spread, px["bid"])

        # ── Route through strategy plugin layer ──────────────────────────
        strategy = get_strategy("ST-A2")
        try:
            signal = strategy.generate_signal(
                {"symbol": symbol, "m15": m15, "h4": h4}
            )
        except Exception as exc:
            _log.warning("Strategy error %s: %s", symbol, exc)
            continue

        if signal is None:
            _log.info("TICK %s  no signal", symbol)
            continue

        # ── Position sizing ──────────────────────────────────────────────
        try:
            acct = await executor.get_account_info()
            balance = acct["balance"]
        except Exception:
            balance = 0.0

        sl_pips = abs(signal.metadata.get("risk_pips", 10))
        lots    = calculate_lots(balance, sl_pips, symbol)

        _log.info(
            "SIGNAL %s %s %s entry=%.5f SL=%.5f TP=%.5f spread=%.1f lots=%.2f conf=%.2f",
            symbol, signal.action, signal.session,
            signal.entry_price, signal.stop_loss, signal.take_profit,
            spread, lots, signal.confidence,
        )

        if dry_run:
            _log.info("DRY_RUN — not placing order.")
            journal.log_open(signal, {"order_id": "DRY", "simulated": True}, lots, spread)
            continue

        # ── Open position ────────────────────────────────────────────────
        order = await manager.open_position(signal, lots)
        journal.log_open(signal, order, lots, spread)
        risk_state["open_positions"] = risk_state.get("open_positions", 0) + 1
        _log.info("Order placed: %s", order.get("order_id"))

    return risk_state


async def run(interval: int, dry_run: bool) -> None:
    _log.info("ST-A2 demo runner starting. DRY_RUN=%s", dry_run)

    connector = MT5Connector(mode="demo")
    try:
        await connector.connect()
    except Exception as exc:
        _log.error("Connection failed: %s", exc)
        return

    executor   = VantageDemoExecutor(connector)
    manager    = TradeManager(executor)
    journal    = DemoTradeJournal()
    risk_state = new_state()

    try:
        while True:
            try:
                risk_state = await _tick(executor, manager, journal, risk_state, dry_run)
            except Exception as exc:
                _log.error("Tick error: %s", exc, exc_info=True)
            await asyncio.sleep(interval)
    finally:
        _log.info("Shutting down.")
        await connector.disconnect()


def main() -> None:
    parser = argparse.ArgumentParser(description="ST-A2 Vantage demo runner")
    parser.add_argument("--interval", type=int, default=INTERVAL)
    parser.add_argument("--dry-run",  action="store_true", default=True)
    parser.add_argument("--live",     action="store_true",
                        help="Disable dry-run (still requires DEMO_ONLY=false in .env)")
    args = parser.parse_args()
    dry = not args.live
    asyncio.run(run(args.interval, dry))


if __name__ == "__main__":
    main()
