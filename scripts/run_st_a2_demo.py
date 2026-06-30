"""
Vantage demo runner for strategy adapters.

Legacy entrypoint kept for backwards compatibility.
Preferred command:
    python3 scripts/run_strategy_demo.py

Execution modes (TRADING_MODE env var or --mode flag):

  shadow  Generate signals, run all controls, size positions — NO broker order.
          Signals logged to logs/shadow_trades.jsonl.

  demo    Complete pipeline, send orders to Vantage demo account.
          Requires DEMO_ONLY=false in .env.

  live    BLOCKED. LIVE_TRADING stays False until Phase-0 + 30-day demo
          validation. This mode prints an error and exits.

Pipeline per tick:
  MarketData → [signals] → SignalRouter → CircuitBreaker → PortfolioManager → Execute

Usage:
    TRADING_MODE=shadow python3 scripts/run_strategy_demo.py
    TRADING_MODE=demo   python3 scripts/run_strategy_demo.py
    python3 scripts/run_strategy_demo.py --strategy SMCOrderBlockFVGSession --mode shadow --once
"""

from __future__ import annotations

import argparse
import asyncio
import json
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
from core.strategy_registry import register_strategy, get_strategy  # noqa: E402
from strategies.adapters import ADAPTER_TYPES, build_strategy  # noqa: E402

# ── Portfolio control layer ───────────────────────────────────────────────────
from core.signal_router import SignalRouter  # noqa: E402
from core.circuit_breaker import CircuitBreaker  # noqa: E402
from core.portfolio_manager import PortfolioManager  # noqa: E402
from strategies.shadow_tracker import ShadowTracker  # noqa: E402

_router = SignalRouter()
_breaker = CircuitBreaker()
_portmgr = PortfolioManager()
_shadow = ShadowTracker()

# ── Trade journal (SQLite) ────────────────────────────────────────────────────
from core.trade_journal_db import TradeJournalDB  # noqa: E402

_journal_db = TradeJournalDB()

# ── Demo execution stack ──────────────────────────────────────────────────────
from execution.mt5_connector import MT5Connector  # noqa: E402
from execution.vantage_demo_executor import VantageDemoExecutor  # noqa: E402
from execution.trade_manager import TradeManager  # noqa: E402
from execution.demo_risk_manager import (  # noqa: E402
    calculate_lots,
    new_state,
    check_limits,
    reset_daily,
)
from execution.trade_journal import DemoTradeJournal  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(Path("logs") / "strategy_demo.log"),
    ],
)
for _noisy in ("engineio", "socketio", "engineio.client", "socketio.client", "httpx"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)
_log = logging.getLogger("strategy_demo.runner")

# Default SMC OB + FVG demo universe from the registered strategy spec
PAIRS = ["EURUSD", "GBPUSD", "XAUUSD"]
INTERVAL = 60  # seconds
MAX_SPREAD_PIPS: dict[str, float] = {"EURUSD": 1.5, "GBPUSD": 2.0, "XAUUSD": 3.0}
_MAX_FETCH_FAILURES = 3
_STATE_PATH = Path("logs") / "strategy_demo_state.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _session_gate(now: datetime | None = None) -> str:
    ts = now or datetime.now(timezone.utc)
    hm = ts.hour * 60 + ts.minute
    if 7 * 60 <= hm < 11 * 60:
        return "london"
    if 12 * 60 <= hm < 16 * 60:
        return "new_york"
    if 0 <= hm < 8 * 60:
        return "asian"
    return "closed"


def _write_state(payload: dict) -> None:
    try:
        _STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = dict(payload)
        payload["updated_at"] = _now_iso()
        _STATE_PATH.write_text(
            json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
        )
    except Exception as exc:
        _log.debug("State write skipped: %s", exc)


def _base_state(mode: str, strategy_name: str, interval: int, once: bool) -> dict:
    return {
        "runner": "strategy_demo",
        "pid": os.getpid(),
        "account_mode": "demo",
        "mode": mode,
        "strategy": strategy_name,
        "interval_seconds": interval,
        "once": once,
        "demo_only": os.environ.get("DEMO_ONLY", "true").lower()
        not in ("false", "0", "no"),
        "live_trading": os.environ.get("LIVE_TRADING", "false").lower() == "true",
        "pairs": PAIRS,
        "max_spread_pips": MAX_SPREAD_PIPS,
        "session_gate": _session_gate(),
        "started_at": _now_iso(),
        "status": "starting",
        "last_tick_at": "",
        "last_decision": "starting",
        "last_error": "",
        "pair_results": [],
        "last_signal": None,
        "open_positions": [],
        "account": {},
    }


async def _tick(
    mode: str,
    strategy_name: str,
    connector: MT5Connector,
    executor: VantageDemoExecutor,
    manager: TradeManager,
    journal: DemoTradeJournal,
    risk_state: dict,
) -> dict:
    """One scan cycle. Returns updated risk_state."""
    state = dict(risk_state.get("_dashboard_state") or {})
    state.update(
        {
            "status": "running",
            "last_error": "",
            "last_tick_at": _now_iso(),
            "last_decision": "scanning",
            "session_gate": _session_gate(),
            "pair_results": [],
        }
    )

    # Daily reset
    from datetime import date

    today = date.today().isoformat()
    if risk_state.get("last_reset", "")[:10] != today:
        risk_state = reset_daily(risk_state)
        _log.info("Daily risk state reset.")
        state["daily_reset_at"] = _now_iso()

    # Portfolio-level loss guard
    if _portmgr.any_loss_limit_hit():
        _log.warning("Portfolio loss limit hit — skipping tick. %s", _portmgr.stats())
        state["status"] = "blocked"
        state["last_decision"] = "portfolio_loss_limit"
        state["portfolio_stats"] = _portmgr.stats()
        risk_state["_dashboard_state"] = state
        _write_state(state)
        return risk_state

    # ── Phase 1: Gather market data ────────────────────────────────────────
    fetch_fails = risk_state.get("_fetch_fails", 0)
    ready: list[dict] = []

    for symbol in PAIRS:
        try:
            m15 = await executor.get_candles(symbol, "M15", 200)
            h4 = await executor.get_candles(symbol, "H4", 100)
            px = await executor.get_price(symbol)
            fetch_fails = 0
        except Exception as exc:
            _log.warning("Data fetch error %s: %s", symbol, exc)
            fetch_fails += 1
            state["pair_results"].append(
                {
                    "symbol": symbol,
                    "status": "error",
                    "error": str(exc),
                    "fetch_failures": fetch_fails,
                }
            )
            if fetch_fails >= _MAX_FETCH_FAILURES:
                _log.warning(
                    "Consecutive fetch failures=%d — reconnecting", fetch_fails
                )
                try:
                    await connector.reconnect()
                    fetch_fails = 0
                    state["last_decision"] = "reconnected"
                except Exception as re_exc:
                    _log.error("Reconnect failed: %s", re_exc)
                    state["status"] = "error"
                    state["last_error"] = str(re_exc)
            continue

        spread = px["spread_pips"]
        max_sp = MAX_SPREAD_PIPS.get(symbol, 2.0)
        if spread > max_sp:
            _log.info("SKIP %s — spread %.1f > %.1f", symbol, spread, max_sp)
            state["pair_results"].append(
                {
                    "symbol": symbol,
                    "status": "skipped",
                    "reason": "spread_limit",
                    "spread_pips": spread,
                    "max_spread_pips": max_sp,
                    "price": px["bid"],
                    "bars": len(m15),
                }
            )
            continue

        if len(m15) < 50:
            _log.debug("Insufficient bars %s", symbol)
            state["pair_results"].append(
                {
                    "symbol": symbol,
                    "status": "skipped",
                    "reason": "insufficient_bars",
                    "bars": len(m15),
                }
            )
            continue

        _log.info(
            "TICK %s  bars=%d  spread=%.1fpip  price=%.5f",
            symbol,
            len(m15),
            spread,
            px["bid"],
        )
        state["pair_results"].append(
            {
                "symbol": symbol,
                "status": "ready",
                "bars": len(m15),
                "spread_pips": spread,
                "price": px["bid"],
            }
        )
        ready.append(
            {"symbol": symbol, "m15": m15, "h4": h4, "spread": spread, "px": px}
        )

    risk_state["_fetch_fails"] = fetch_fails

    if not ready:
        state["last_decision"] = "no_ready_pairs"
        risk_state["_dashboard_state"] = state
        _write_state(state)
        return risk_state

    # ── Phase 2: Generate signals ──────────────────────────────────────────
    raw_signals = []
    for item in ready:
        strategy = get_strategy(strategy_name)
        if strategy is None:
            continue
        try:
            sig = strategy.generate_signal(
                {
                    "symbol": item["symbol"],
                    "m15": item["m15"],
                    "h4": item["h4"],
                    "spread_pips": item["spread"],
                }
            )
        except Exception as exc:
            _log.warning("Strategy error %s: %s", item["symbol"], exc)
            continue

        if sig is not None:
            raw_signals.append(sig)

    if not raw_signals:
        _log.info("No signals this tick.")
        state["last_decision"] = "no_signals"
        try:
            state["account"] = await executor.get_account_info()
        except Exception:
            pass
        try:
            positions = await manager.get_positions()
            state["open_positions"] = positions
        except Exception:
            state["open_positions"] = []
        risk_state["_dashboard_state"] = state
        _write_state(state)
        return risk_state

    # ── Phase 3: SignalRouter — validate, dedup ────────────────────────────
    routed = _router.route(raw_signals)
    if not routed:
        _log.info("SignalRouter: all signals rejected.")
        state["last_decision"] = "router_rejected"
        risk_state["_dashboard_state"] = state
        _write_state(state)
        return risk_state

    # ── Phase 4: CircuitBreaker ────────────────────────────────────────────
    cb_approved = []
    for sig in routed:
        ok, reason = _breaker.check(sig.strategy_name)
        if not ok:
            _log.info(
                "CircuitBreaker blocked %s/%s: %s",
                sig.strategy_name,
                sig.symbol,
                reason,
            )
            _journal_db.record_signal(
                sig,
                router_result="PASS",
                breaker_result=f"BLOCKED: {reason}",
                portfolio_result="SKIPPED",
                execution_result="SKIPPED",
            )
        else:
            cb_approved.append(sig)

    if not cb_approved:
        state["last_decision"] = "breaker_blocked"
        risk_state["_dashboard_state"] = state
        _write_state(state)
        return risk_state

    # ── Phase 5: PortfolioManager ──────────────────────────────────────────
    pm_approved = _portmgr.evaluate(cb_approved)
    for sig in cb_approved:
        if sig not in pm_approved:
            _journal_db.record_signal(
                sig,
                router_result="PASS",
                breaker_result="PASS",
                portfolio_result="BLOCKED",
                execution_result="SKIPPED",
            )

    if not pm_approved:
        _log.info("PortfolioManager blocked all signals. %s", _portmgr.stats())
        state["last_decision"] = "portfolio_blocked"
        state["portfolio_stats"] = _portmgr.stats()
        risk_state["_dashboard_state"] = state
        _write_state(state)
        return risk_state

    # ── Phase 6: Execute ───────────────────────────────────────────────────
    spread_by_symbol = {item["symbol"]: item["spread"] for item in ready}

    try:
        acct = await executor.get_account_info()
        balance = acct["balance"]
        state["account"] = acct
    except Exception:
        balance = 0.0

    for signal in pm_approved:
        limit = check_limits(risk_state)
        if not limit["approved"]:
            _log.info("SKIP %s — %s", signal.symbol, limit["reason"])
            state["last_decision"] = f"risk_blocked:{limit['reason']}"
            _journal_db.record_signal(
                signal,
                router_result="PASS",
                breaker_result="PASS",
                portfolio_result="PASS",
                execution_result=f"BLOCKED: {limit['reason']}",
            )
            continue

        sl_pips = abs(signal.metadata.get("risk_pips", 10))
        lots = calculate_lots(balance, sl_pips, signal.symbol)
        spread = spread_by_symbol.get(signal.symbol, 0.0)

        _log.info(
            "SIGNAL [%s] %s %s %s entry=%.5f SL=%.5f TP=%.5f spread=%.1f lots=%.2f conf=%.2f",
            mode.upper(),
            signal.symbol,
            signal.action,
            signal.session,
            signal.entry_price,
            signal.stop_loss,
            signal.take_profit,
            spread,
            lots,
            signal.confidence,
        )
        state["last_signal"] = {
            "timestamp": _now_iso(),
            "symbol": signal.symbol,
            "action": signal.action,
            "session": signal.session,
            "entry_price": signal.entry_price,
            "stop_loss": signal.stop_loss,
            "take_profit": signal.take_profit,
            "spread_pips": spread,
            "lots": lots,
            "confidence": signal.confidence,
            "risk_pips": signal.metadata.get("risk_pips"),
            "reward_pips": signal.metadata.get("reward_pips"),
            "rr": signal.metadata.get("rr"),
        }

        _breaker.record_signal(signal.strategy_name)

        if mode == "shadow":
            # Shadow mode: log signal, no broker order
            _shadow.track(signal, reason="shadow_mode")
            _journal_db.record_signal(
                signal,
                router_result="PASS",
                breaker_result="PASS",
                portfolio_result="PASS",
                execution_result="SHADOW",
                position_size=lots,
            )
            journal.log_open(
                signal, {"order_id": "SHADOW", "simulated": True}, lots, spread
            )
            _portmgr.record_trade(signal)
            _log.info("SHADOW — signal recorded, no order sent.")
            state["status"] = "signal"
            state["last_decision"] = "shadow_signal"
            state["last_signal"]["simulated"] = True
            continue

        # Demo mode: send to broker
        try:
            order = await manager.open_position(signal, lots)
            journal.log_open(signal, order, lots, spread)
            trade_id = _journal_db.record_signal(
                signal,
                router_result="PASS",
                breaker_result="PASS",
                portfolio_result="PASS",
                execution_result="OPEN",
                broker_order_id=order.get("order_id", ""),
                position_size=lots,
            )
            _portmgr.record_trade(signal)
            risk_state["open_positions"] = risk_state.get("open_positions", 0) + 1
            _log.info(
                "Order placed: %s (journal_id=%s)", order.get("order_id"), trade_id
            )
            state["status"] = "signal"
            state["last_decision"] = "order_opened"
            state["last_signal"]["order_id"] = order.get("order_id", "")
            state["last_signal"]["simulated"] = order.get("simulated", False)
        except Exception as exc:
            _log.error("Order placement failed %s: %s", signal.symbol, exc)
            state["status"] = "error"
            state["last_decision"] = "order_error"
            state["last_error"] = str(exc)
            _journal_db.record_signal(
                signal,
                router_result="PASS",
                breaker_result="PASS",
                portfolio_result="PASS",
                execution_result=f"ERROR: {exc}",
                position_size=lots,
            )

    try:
        state["open_positions"] = await manager.get_positions()
    except Exception as exc:
        state["open_positions_error"] = str(exc)
    risk_state["_dashboard_state"] = state
    _write_state(state)
    return risk_state


async def run(mode: str, interval: int, strategy_name: str, once: bool = False) -> None:
    state = _base_state(mode, strategy_name, interval, once)
    _log.info(
        "Vantage runner starting. strategy=%s mode=%s interval=%ds once=%s",
        strategy_name,
        mode.upper(),
        interval,
        once,
    )
    _write_state(state)

    connector = MT5Connector(mode="demo")
    try:
        await connector.connect()
    except Exception as exc:
        _log.error("Connection failed: %s", exc)
        state["status"] = "error"
        state["last_error"] = str(exc)
        state["last_decision"] = "connection_failed"
        _write_state(state)
        return

    executor = VantageDemoExecutor(connector)
    manager = TradeManager(executor)
    journal = DemoTradeJournal()
    risk_state = new_state()
    state["status"] = "connected"
    state["last_decision"] = "connected"
    _write_state(state)

    try:
        while True:
            try:
                risk_state["_dashboard_state"] = dict(
                    risk_state.get("_dashboard_state") or state
                )
                risk_state = await _tick(
                    mode,
                    strategy_name,
                    connector,
                    executor,
                    manager,
                    journal,
                    risk_state,
                )
            except Exception as exc:
                _log.error("Tick error: %s", exc, exc_info=True)
                state = dict(risk_state.get("_dashboard_state") or state)
                state["status"] = "error"
                state["last_error"] = str(exc)
                state["last_decision"] = "tick_error"
                _write_state(state)
            if once:
                break
            await asyncio.sleep(interval)
    finally:
        _log.info("Shutting down.")
        state = dict(risk_state.get("_dashboard_state") or state)
        state["status"] = "stopped"
        state["last_decision"] = "shutdown"
        _write_state(state)
        await connector.disconnect()


def main() -> None:
    env_mode = os.environ.get("TRADING_MODE", "shadow").lower()
    env_strategy = os.environ.get("DEMO_STRATEGY", "ST-A2")

    parser = argparse.ArgumentParser(description="Vantage demo runner")
    parser.add_argument(
        "--mode",
        choices=["shadow", "demo", "live"],
        default=env_mode,
        help="shadow=no orders, demo=Vantage demo orders, live=BLOCKED",
    )
    parser.add_argument(
        "--strategy",
        default=env_strategy,
        choices=sorted(ADAPTER_TYPES),
        help="Registered strategy adapter to run",
    )
    parser.add_argument("--interval", type=int, default=INTERVAL)
    parser.add_argument(
        "--once", action="store_true", help="Run a single scan cycle and exit"
    )
    # Legacy flags for backwards compat
    parser.add_argument(
        "--dry-run", action="store_true", default=False, help="Alias for --mode shadow"
    )
    parser.add_argument(
        "--live", action="store_true", default=False, help="Alias for --mode demo"
    )
    args = parser.parse_args()

    mode = args.mode
    if args.dry_run:
        mode = "shadow"
    if args.live:
        mode = "demo"

    if mode == "live":
        print(
            "ERROR: TRADING_MODE=live is permanently blocked.\n"
            "LIVE_TRADING=false until Phase-0 gate passes AND 30-day demo validation completes.\n"
            "See CLAUDE.md §0 rule 1."
        )
        sys.exit(1)

    register_strategy(build_strategy(args.strategy))
    asyncio.run(run(mode, args.interval, args.strategy, once=args.once))


if __name__ == "__main__":
    main()
