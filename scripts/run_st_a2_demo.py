"""
ST-A2 Demo Runner — shadow/paper execution on Vantage MT5 demo.

Flow per tick:
  MarketData → [signals] → SignalRouter → CircuitBreaker → PortfolioManager → Execute

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

# ── Portfolio control layer ───────────────────────────────────────────────────
from core.signal_router import SignalRouter
from core.circuit_breaker import CircuitBreaker
from core.portfolio_manager import PortfolioManager
from strategies.shadow_tracker import ShadowTracker

_router  = SignalRouter()
_breaker = CircuitBreaker()
_portmgr = PortfolioManager()
_shadow  = ShadowTracker()

# ── Demo execution stack ──────────────────────────────────────────────────────
from execution.mt5_connector       import MT5Connector
from execution.vantage_demo_executor import VantageDemoExecutor
from execution.trade_manager        import TradeManager
from execution.demo_risk_manager    import (
    calculate_lots, new_state, check_limits, record_result, reset_daily,
)
from execution.trade_journal        import DemoTradeJournal

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
_MAX_FETCH_FAILURES = 3   # reconnect after this many consecutive per-tick data failures


async def _tick(
    connector:  MT5Connector,
    executor:   VantageDemoExecutor,
    manager:    TradeManager,
    journal:    DemoTradeJournal,
    risk_state: dict,
    dry_run:    bool,
) -> dict:
    """One scan cycle. Returns updated risk_state."""

    # Daily reset
    from datetime import date
    today = date.today().isoformat()
    if risk_state.get("last_reset", "")[:10] != today:
        risk_state = reset_daily(risk_state)
        _log.info("Daily risk state reset.")

    # ── Portfolio-level loss guard (daily/weekly/monthly) ──────────────────
    if _portmgr.any_loss_limit_hit():
        _log.warning("Portfolio loss limit hit — skipping tick. %s", _portmgr.stats())
        return risk_state

    # ── Phase 1: Gather market data for all pairs ──────────────────────────
    fetch_fails = risk_state.get("_fetch_fails", 0)
    ready: list[dict] = []

    for symbol in PAIRS:
        try:
            m15 = await executor.get_candles(symbol, "M15", 200)
            h4  = await executor.get_candles(symbol, "H4",  100)
            px  = await executor.get_price(symbol)
            fetch_fails = 0
        except Exception as exc:
            _log.warning("Data fetch error %s: %s", symbol, exc)
            fetch_fails += 1
            if fetch_fails >= _MAX_FETCH_FAILURES:
                _log.warning("Consecutive fetch failures=%d — reconnecting", fetch_fails)
                try:
                    await connector.reconnect()
                    fetch_fails = 0
                except Exception as re_exc:
                    _log.error("Reconnect failed: %s", re_exc)
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
        ready.append({"symbol": symbol, "m15": m15, "h4": h4,
                      "spread": spread, "px": px})

    risk_state["_fetch_fails"] = fetch_fails

    if not ready:
        return risk_state

    # ── Phase 2: Generate signals from all strategies ──────────────────────
    raw_signals = []
    for item in ready:
        strategy = get_strategy("ST-A2")
        if strategy is None:
            continue
        try:
            sig = strategy.generate_signal(
                {"symbol": item["symbol"], "m15": item["m15"], "h4": item["h4"]}
            )
        except Exception as exc:
            _log.warning("Strategy error %s: %s", item["symbol"], exc)
            continue

        if sig is not None:
            raw_signals.append(sig)

    if not raw_signals:
        _log.info("No signals this tick.")
        return risk_state

    # ── Phase 3: SignalRouter — validate TTL, geometry, dedup ─────────────
    routed = _router.route(raw_signals)
    if not routed:
        _log.info("SignalRouter: all signals rejected.")
        return risk_state

    # ── Phase 4: CircuitBreaker — per-strategy rate / loss limits ─────────
    cb_approved = []
    for sig in routed:
        ok, reason = _breaker.check(sig.strategy_name)
        if not ok:
            _log.info("CircuitBreaker blocked %s/%s: %s",
                      sig.strategy_name, sig.symbol, reason)
        else:
            cb_approved.append(sig)

    if not cb_approved:
        return risk_state

    # ── Phase 5: PortfolioManager — limits, correlation, trade cap ────────
    pm_approved = _portmgr.evaluate(cb_approved)
    if not pm_approved:
        _log.info("PortfolioManager blocked all signals. %s", _portmgr.stats())
        return risk_state

    # ── Phase 6: Execute approved signals ──────────────────────────────────
    spread_by_symbol = {item["symbol"]: item["spread"] for item in ready}

    try:
        acct    = await executor.get_account_info()
        balance = acct["balance"]
    except Exception:
        balance = 0.0

    for signal in pm_approved:
        # Legacy demo risk manager check (consecutive loss guard etc.)
        limit = check_limits(risk_state)
        if not limit["approved"]:
            _log.info("SKIP %s — %s", signal.symbol, limit["reason"])
            continue

        sl_pips = abs(signal.metadata.get("risk_pips", 10))
        lots    = calculate_lots(balance, sl_pips, signal.symbol)
        spread  = spread_by_symbol.get(signal.symbol, 0.0)

        _log.info(
            "SIGNAL %s %s %s entry=%.5f SL=%.5f TP=%.5f spread=%.1f lots=%.2f conf=%.2f",
            signal.symbol, signal.action, signal.session,
            signal.entry_price, signal.stop_loss, signal.take_profit,
            spread, lots, signal.confidence,
        )

        # Record in circuit breaker rate window
        _breaker.record_signal(signal.strategy_name)

        if dry_run:
            _log.info("DRY_RUN — not placing order.")
            journal.log_open(signal, {"order_id": "DRY", "simulated": True}, lots, spread)
            _portmgr.record_trade(signal)
            continue

        try:
            order = await manager.open_position(signal, lots)
            journal.log_open(signal, order, lots, spread)
            _portmgr.record_trade(signal)
            risk_state["open_positions"] = risk_state.get("open_positions", 0) + 1
            _log.info("Order placed: %s", order.get("order_id"))
        except Exception as exc:
            _log.error("Order placement failed %s: %s", signal.symbol, exc)

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
                risk_state = await _tick(
                    connector, executor, manager, journal, risk_state, dry_run
                )
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
