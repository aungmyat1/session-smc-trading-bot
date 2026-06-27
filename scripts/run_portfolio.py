"""
Multi-Strategy Portfolio Runner — 4-8 trades/day target.

Strategies (demo execution):
  ST-A2          — EURUSD, GBPUSD        (session sweep + SMC confirmation)
  LondonBreakout — EURUSD, GBPUSD, USDJPY (Asian range breakout + retest)
  NYMomentum     — EURUSD, GBPUSD, USDJPY (NY sweep of London levels)

Strategies (shadow — signal log only, no orders):
  AdaptiveSMC    — EURUSD, GBPUSD
  VWAPBreakout   — EURUSD, GBPUSD

Pipeline per tick:
  1. Fetch M15+H4 once per symbol (shared across strategies)
  2. Generate signals: each strategy × its supported pairs
  3. Tag signals with execution_mode from config
  4. SignalRouter  — validate TTL, geometry, resolve conflicts
  5. CircuitBreaker — per-strategy rate + consecutive loss guard
  6. PortfolioManager — daily/weekly limits, correlation, trade cap
  7. Execute: demo → broker order | shadow → ShadowTracker + journal

Execution modes (TRADING_MODE env var or --mode flag):
  shadow  — all strategies log only, no orders
  demo    — strategies execute per config (demo/shadow per strategy)
  live    — BLOCKED (CLAUDE.md §0)

Usage:
    TRADING_MODE=shadow python3 scripts/run_portfolio.py
    TRADING_MODE=demo   python3 scripts/run_portfolio.py
    python3 scripts/run_portfolio.py --mode demo --interval 60
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

# ── Register all strategies ───────────────────────────────────────────────────
from core.strategy_registry import register_strategy, get_strategy
from strategies.adapters.st_a2_adapter      import ST2Adapter
from strategies.adapters.london_breakout_adapter import LondonBreakoutAdapter
from strategies.adapters.ny_momentum_adapter     import NYMomentumAdapter
from strategies.adapters.adaptive_smc_adapter    import AdaptiveSMCAdapter
from strategies.adapters.vwap_adapter            import (
    VWAPMeanReversionAdapter,
    VWAPBreakoutAdapter,
)

for _adapter in [
    ST2Adapter(),
    LondonBreakoutAdapter(),
    NYMomentumAdapter(),
    AdaptiveSMCAdapter(),
    VWAPMeanReversionAdapter(),
    VWAPBreakoutAdapter(),
]:
    register_strategy(_adapter)

# ── Portfolio control layer ───────────────────────────────────────────────────
from core.signal_router     import SignalRouter
from core.circuit_breaker   import CircuitBreaker
from core.portfolio_manager import PortfolioManager
from strategies.shadow_tracker import ShadowTracker
from core.trade_journal_db  import TradeJournalDB

_router   = SignalRouter()
_breaker  = CircuitBreaker()
_portmgr  = PortfolioManager()
_shadow   = ShadowTracker()
_jdb      = TradeJournalDB()

# ── Execution stack ───────────────────────────────────────────────────────────
from execution.mt5_connector          import MT5Connector
from execution.vantage_demo_executor  import VantageDemoExecutor
from execution.trade_manager          import TradeManager
from execution.demo_risk_manager      import calculate_lots, new_state, check_limits, reset_daily
from execution.trade_journal          import DemoTradeJournal

# ── Strategy × pairs matrix (read from config/strategy_portfolio.yaml) ────────
#    Fallback hardcoded if yaml unavailable.

def _load_strategy_config() -> dict:
    try:
        import yaml  # type: ignore
        cfg_path = _ROOT / "config" / "strategy_portfolio.yaml"
        with cfg_path.open() as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}

_CFG = _load_strategy_config()
_STRAT_CFG: dict = _CFG.get("strategies", {})

# Per-strategy: pairs and execution mode
_STRATEGY_MAP: dict[str, dict] = {
    name: {
        "pairs": cfg.get("pairs", ["EURUSD", "GBPUSD"]),
        "mode":  cfg.get("execution_mode", "shadow"),
        "enabled": cfg.get("enabled", True),
        "config": cfg,
    }
    for name, cfg in _STRAT_CFG.items()
    if cfg.get("enabled", True)
} or {
    # Hardcoded fallback
    "ST-A2":              {"pairs": ["EURUSD", "GBPUSD", "XAUUSD"], "mode": "demo",   "enabled": True, "config": {}},
    "LondonBreakout":     {"pairs": ["EURUSD", "GBPUSD", "XAUUSD"], "mode": "demo",   "enabled": True, "config": {}},
    "NYMomentum":         {"pairs": ["EURUSD", "GBPUSD", "XAUUSD"], "mode": "demo",   "enabled": True, "config": {}},
    "AdaptiveSMC":        {"pairs": ["EURUSD", "GBPUSD", "XAUUSD"], "mode": "shadow", "enabled": True, "config": {}},
    "VWAPMeanReversion":  {"pairs": ["EURUSD", "GBPUSD", "XAUUSD"], "mode": "shadow", "enabled": True, "config": {}},
    "VWAPBreakout":       {"pairs": ["EURUSD", "GBPUSD", "XAUUSD"], "mode": "shadow", "enabled": True, "config": {}},
}

if "VWAPMeanReversion" in _STRATEGY_MAP and "VWAPBreakout" not in _STRATEGY_MAP:
    _STRATEGY_MAP["VWAPBreakout"] = {
        **_STRATEGY_MAP["VWAPMeanReversion"],
        "enabled": False,
        "alias_for": "VWAPMeanReversion",
    }

_ALL_SYMBOLS: list[str] = sorted({
    sym for cfg in _STRATEGY_MAP.values() for sym in cfg["pairs"]
})

# Strategies requiring H4 data
_NEEDS_H4 = {"ST-A2", "AdaptiveSMC"}

# Spread limits per symbol
_MAX_SPREAD = {"EURUSD": 1.5, "GBPUSD": 2.0, "USDJPY": 1.5, "XAUUSD": 3.0}

_MAX_FETCH_FAIL = 3

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(Path("logs") / "portfolio_runner.log"),
    ],
)
for _noisy in ("engineio", "socketio", "engineio.client", "socketio.client", "httpx"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)
_log = logging.getLogger("portfolio.runner")

INTERVAL = 60


# ── Tick ──────────────────────────────────────────────────────────────────────

async def _tick(
    global_mode: str,
    connector:   MT5Connector,
    executor:    VantageDemoExecutor,
    manager:     TradeManager,
    journal:     DemoTradeJournal,
    risk_state:  dict,
) -> dict:

    # Daily reset
    from datetime import date
    today = date.today().isoformat()
    if risk_state.get("last_reset", "")[:10] != today:
        risk_state = reset_daily(risk_state)
        _log.info("Daily risk state reset.")

    # Portfolio loss guard
    if _portmgr.any_loss_limit_hit():
        _log.warning("Portfolio loss limit hit — skipping tick. %s", _portmgr.stats())
        return risk_state

    # ── Phase 1: Fetch market data (once per symbol) ───────────────────────
    fetch_fails = risk_state.get("_fetch_fails", 0)
    market: dict[str, dict] = {}

    for symbol in _ALL_SYMBOLS:
        try:
            m15  = await executor.get_candles(symbol, "M15", 200)
            h4   = await executor.get_candles(symbol, "H4",  100)
            px   = await executor.get_price(symbol)
            fetch_fails = 0
        except Exception as exc:
            _log.warning("Fetch error %s: %s", symbol, exc)
            fetch_fails += 1
            if fetch_fails >= _MAX_FETCH_FAIL:
                _log.warning("Consecutive failures=%d — reconnecting", fetch_fails)
                try:
                    await connector.reconnect()
                    fetch_fails = 0
                except Exception as re_exc:
                    _log.error("Reconnect failed: %s", re_exc)
            continue

        spread   = px["spread_pips"]
        max_sp   = _MAX_SPREAD.get(symbol, 2.0)
        if spread > max_sp:
            _log.info("SKIP %s spread=%.1f > %.1f", symbol, spread, max_sp)
            continue
        if len(m15) < 50:
            _log.debug("Insufficient bars %s", symbol)
            continue

        _log.info("DATA %s  bars=%d  spread=%.1fpip  price=%.5f",
                  symbol, len(m15), spread, px["bid"])
        market[symbol] = {"m15": m15, "h4": h4, "spread": spread, "px": px}

    risk_state["_fetch_fails"] = fetch_fails

    if not market:
        return risk_state

    # ── Phase 2: Generate signals — all strategies × their pairs ──────────
    raw_signals = []

    for strategy_name, scfg in _STRATEGY_MAP.items():
        if not scfg.get("enabled", True):
            continue
        strategy = get_strategy(strategy_name)
        if strategy is None:
            continue

        for symbol in scfg["pairs"]:
            if symbol not in market:
                continue

            data = {
                "symbol": symbol,
                "m15":    market[symbol]["m15"],
                "h4":     market[symbol]["h4"] if strategy_name in _NEEDS_H4 else [],
                "spread_pips": market[symbol]["spread"],
            }

            try:
                sig = strategy.generate_signal({**data, "config": scfg.get("config", {})})
            except Exception as exc:
                _log.warning("%s/%s generate error: %s", strategy_name, symbol, exc)
                continue

            if sig is not None:
                # Tag with execution_mode so the executor knows demo vs shadow
                sig.metadata["execution_mode"] = scfg["mode"]
                raw_signals.append(sig)

    if not raw_signals:
        _log.info("No signals this tick (%d symbols scanned, %d strategies)",
                  len(market), len(_STRATEGY_MAP))
        return risk_state

    _log.info("Generated %d raw signal(s)", len(raw_signals))

    # ── Phase 3: SignalRouter — TTL, geometry, conflict resolution ─────────
    routed = _router.route(raw_signals)
    if not routed:
        _log.info("SignalRouter: all signals rejected.")
        return risk_state

    # ── Phase 4: CircuitBreaker — per-strategy rate + loss cooldown ────────
    cb_approved = []
    for sig in routed:
        ok, reason = _breaker.check(sig.strategy_name)
        if not ok:
            _log.info("CB blocked %s/%s: %s", sig.strategy_name, sig.symbol, reason)
            _jdb.record_signal(sig, router_result="PASS",
                               breaker_result=f"BLOCKED:{reason}",
                               portfolio_result="SKIPPED",
                               execution_result="SKIPPED")
        else:
            cb_approved.append(sig)

    if not cb_approved:
        return risk_state

    # ── Phase 5: PortfolioManager — limits, correlation, cap ──────────────
    pm_approved = _portmgr.evaluate(cb_approved)
    for sig in cb_approved:
        if sig not in pm_approved:
            _jdb.record_signal(sig, router_result="PASS", breaker_result="PASS",
                               portfolio_result="BLOCKED", execution_result="SKIPPED")
    if not pm_approved:
        _log.info("PortfolioManager blocked all. %s", _portmgr.stats())
        return risk_state

    # ── Phase 6: Execute ───────────────────────────────────────────────────
    try:
        balance = (await executor.get_account_info())["balance"]
    except Exception:
        balance = 0.0

    for signal in pm_approved:
        limit = check_limits(risk_state)
        if not limit["approved"]:
            _log.info("SKIP %s/%s — %s", signal.strategy_name, signal.symbol, limit["reason"])
            continue

        sl_pips  = abs(signal.metadata.get("risk_pips", 10))
        lots     = calculate_lots(balance, sl_pips, signal.symbol)
        spread   = market.get(signal.symbol, {}).get("spread", 0.0)

        # Determine final execution mode (global shadow overrides per-strategy demo)
        exec_mode = signal.metadata.get("execution_mode", "shadow")
        if global_mode == "shadow":
            exec_mode = "shadow"

        _log.info(
            "SIGNAL [%s] %s/%s %s entry=%.5f SL=%.5f TP=%.5f "
            "spread=%.1fpip lots=%.2f conf=%.2f",
            exec_mode.upper(), signal.strategy_name, signal.symbol, signal.action,
            signal.entry_price, signal.stop_loss, signal.take_profit,
            spread, lots, signal.confidence,
        )

        _breaker.record_signal(signal.strategy_name)

        if exec_mode == "shadow":
            _shadow.track(signal, reason=f"shadow:{signal.strategy_name}")
            _jdb.record_signal(signal, router_result="PASS", breaker_result="PASS",
                               portfolio_result="PASS", execution_result="SHADOW",
                               position_size=lots)
            journal.log_open(signal, {"order_id": "SHADOW", "simulated": True}, lots, spread)
            _portmgr.record_trade(signal)
            _log.info("SHADOW %s/%s recorded.", signal.strategy_name, signal.symbol)
            continue

        # Demo execution
        try:
            order = await manager.open_position(signal, lots)
            journal.log_open(signal, order, lots, spread)
            _jdb.record_signal(signal, router_result="PASS", breaker_result="PASS",
                               portfolio_result="PASS", execution_result="OPEN",
                               broker_order_id=order.get("order_id", ""),
                               position_size=lots)
            _portmgr.record_trade(signal)
            _breaker.record_trade(signal.strategy_name, won=True)  # open = neutral
            risk_state["open_positions"] = risk_state.get("open_positions", 0) + 1
            _log.info("ORDER %s/%s placed: %s",
                      signal.strategy_name, signal.symbol, order.get("order_id"))
        except Exception as exc:
            _log.error("Order failed %s/%s: %s", signal.strategy_name, signal.symbol, exc)
            _jdb.record_signal(signal, router_result="PASS", breaker_result="PASS",
                               portfolio_result="PASS",
                               execution_result=f"ERROR:{exc}",
                               position_size=lots)

    return risk_state


# ── Main loop ─────────────────────────────────────────────────────────────────

async def run(mode: str, interval: int) -> None:
    _log.info("Portfolio runner starting. MODE=%s  strategies=%s  symbols=%s",
              mode.upper(), list(_STRATEGY_MAP), _ALL_SYMBOLS)

    connector = MT5Connector(mode="demo")
    try:
        await connector.connect()
    except Exception as exc:
        _log.error("Connection failed: %s", exc)
        return

    executor   = VantageDemoExecutor(connector)
    manager    = TradeManager(executor)
    journal    = DemoTradeJournal(Path("logs") / "portfolio_demo_trades.jsonl")
    risk_state = new_state()

    try:
        while True:
            try:
                risk_state = await _tick(mode, connector, executor, manager,
                                         journal, risk_state)
            except Exception as exc:
                _log.error("Tick error: %s", exc, exc_info=True)
            await asyncio.sleep(interval)
    finally:
        _log.info("Shutting down.")
        await connector.disconnect()


def main() -> None:
    env_mode = os.environ.get("TRADING_MODE", "shadow").lower()

    parser = argparse.ArgumentParser(description="Multi-strategy portfolio runner")
    parser.add_argument("--mode", choices=["shadow", "demo", "live"],
                        default=env_mode)
    parser.add_argument("--interval", type=int, default=INTERVAL)
    parser.add_argument("--dry-run", action="store_true", default=False,
                        help="Alias for --mode shadow")
    args = parser.parse_args()

    mode = args.mode
    if args.dry_run:
        mode = "shadow"

    if mode == "live":
        print(
            "ERROR: TRADING_MODE=live is permanently blocked.\n"
            "LIVE_TRADING stays False until Phase-0 + 30-day demo pass.\n"
            "See CLAUDE.md §0 rule 1."
        )
        sys.exit(1)

    asyncio.run(run(mode, args.interval))


if __name__ == "__main__":
    main()
