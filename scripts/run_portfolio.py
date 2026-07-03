# ruff: noqa: E402
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

from approval_package.package_validator import validate_package
from scripts.validate_strategy_identity import package_strategy_id, package_symbols, validate_strategy_identity
from shared.configuration.symbols import validate_symbol
from shared.serialization import append_jsonl

try:
    from dotenv import load_dotenv
    load_dotenv(_ROOT / ".env")
except ImportError:
    pass

# ── Register all strategies ───────────────────────────────────────────────────
from core.strategy_registry import register_strategy, get_strategy
from strategies.adapters.st_a2_adapter      import ST2Adapter
try:
    from strategies.adapters.day_trading_maneuvers_adapter import DayTradingManeuversAdapter
except ImportError:  # Optional adapter is not part of the canonical runtime.
    DayTradingManeuversAdapter = None
from strategies.adapters.london_breakout_adapter import LondonBreakoutAdapter
from strategies.adapters.ny_momentum_adapter     import NYMomentumAdapter
from strategies.adapters.adaptive_smc_adapter    import AdaptiveSMCAdapter
from strategies.adapters.vwap_adapter            import (
    VWAPMeanReversionAdapter,
    VWAPBreakoutAdapter,
)

for _adapter_type in [
    ST2Adapter(),
    DayTradingManeuversAdapter() if DayTradingManeuversAdapter is not None else None,
    LondonBreakoutAdapter(),
    NYMomentumAdapter(),
    AdaptiveSMCAdapter(),
    VWAPMeanReversionAdapter(),
    VWAPBreakoutAdapter(),
]:
    if _adapter_type is not None:
        register_strategy(_adapter_type)

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
from execution.demo_risk_manager      import DEFAULT_RISK_PCT, calculate_lots, new_state, check_limits, reset_daily
from execution.trade_journal          import DemoTradeJournal
from production.engine import (
    AdapterResult,
    CanonicalExecutionPipeline,
    DemoExecutionAdapter,
    ExecutionIntent,
    ExecutionMode,
    RiskDecision,
    RuntimeAuthority,
    RuntimeContext,
    TradeManager,
    VirtualDemoExecutionAdapter,
)

# ── Strategy × pairs matrix (read from config/strategy_portfolio.yaml) ────────
#    Fallback hardcoded if yaml unavailable.

def _load_strategy_config() -> dict:
    try:
        import yaml
        cfg_path = _ROOT / "config" / "strategy_portfolio.yaml"
        with cfg_path.open() as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def _resolve_strategy_package(args: argparse.Namespace) -> str | None:
    package_path = args.strategy_package or os.environ.get("APPROVED_STRATEGY_PACKAGE", "")
    return package_path.strip() or None


def _ensure_strategy_package(
    package_path: str | None,
    runner_strategy_id: str | None = None,
    *,
    signing_key: str | None = None,
    root: Path = _ROOT,
    registry_root: Path | str | None = None,
) -> str:
    if not package_path:
        raise PermissionError(
            "approved strategy package is required for demo execution"
        )
    effective_signing_key = signing_key
    if effective_signing_key is None and Path(package_path).is_file():
        effective_signing_key = os.environ.get("SVOS_PACKAGE_VERIFYING_PUBLIC_KEY", "")
    result = validate_package(package_path, signing_key=effective_signing_key)
    if not result.valid:
        raise PermissionError("approved package rejected: " + "; ".join(result.reasons))
    symbols = package_symbols(package_path)
    if Path(package_path).is_file() and not symbols:
        raise PermissionError("approved package rejected: package symbols are missing")
    for symbol in symbols:
        symbol_result = validate_symbol(symbol, scope="execution")
        if not symbol_result.valid:
            raise PermissionError("approved package rejected: " + "; ".join(symbol_result.errors))
    strategy_id = (runner_strategy_id or package_strategy_id(package_path)).strip()
    identity = validate_strategy_identity(
        root=root,
        package_path=package_path,
        runner_strategy_id=strategy_id,
        registry_root=registry_root,
    )
    identity.require_valid()
    _log.info("Approved strategy package accepted: %s", result.package_path)
    return identity.strategy_id

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
_NEEDS_DTM_DATA = {"DayTradingManeuvers"}

# Spread limits per symbol
_MAX_SPREAD = {"EURUSD": 1.5, "GBPUSD": 2.0, "USDJPY": 1.5, "XAUUSD": 3.0}

_MAX_FETCH_FAIL = 3
_CANDLE_LIMITS = {"M5": 150, "M15": 200, "H1": 180, "H4": 100, "D1": 120}

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


def _signal_timestamp_text(value: object) -> str:
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except TypeError:
            pass
    return str(value)


def _normalize_risk_percent(value: object, default: float) -> float:
    try:
        risk_pct = float(value)
    except (TypeError, ValueError):
        return default
    return risk_pct / 100.0 if risk_pct > 0.05 else risk_pct


def _emit_runtime_event(event_type: str, **details: object) -> None:
    append_jsonl(
        _ROOT / "logs" / "runtime_events.jsonl",
        {"event_type": event_type, "timestamp": datetime.now(timezone.utc).isoformat(), **details},
    )


def _active_strategy_names(allowed_strategy_id: str | None = None) -> list[str]:
    names: list[str] = []
    for strategy_name, scfg in _STRATEGY_MAP.items():
        if allowed_strategy_id and strategy_name != allowed_strategy_id:
            continue
        if not scfg.get("enabled", True):
            continue
        names.append(strategy_name)
    return names


def _required_timeframes(strategy_names: list[str]) -> set[str]:
    required = {"M15"}
    if any(name in _NEEDS_H4 for name in strategy_names):
        required.add("H4")
    if any(name in _NEEDS_DTM_DATA for name in strategy_names):
        required.update({"D1", "H1", "M5"})
    return required


async def evaluate_execution_intent(
    intent: ExecutionIntent,
    *,
    risk_state: dict | None,
    manager: TradeManager | None,
) -> RiskDecision:
    if not isinstance(risk_state, dict):
        return RiskDecision(False, "runtime risk state is unavailable")

    result = check_limits(risk_state)
    if not bool(result["approved"]):
        return RiskDecision(False, str(result["reason"]), result)

    signal = intent.metadata.get("signal")
    signal_metadata = getattr(signal, "metadata", {}) if signal is not None else {}
    spread = float(intent.metadata.get("spread", 0.0) or 0.0)
    max_spread = float(signal_metadata.get("max_spread_pips", 0.0) or 0.0)
    if max_spread and spread > max_spread:
        return RiskDecision(
            False,
            "MAX_SPREAD_EXCEEDED",
            {"spread_pips": spread, "max_spread_pips": max_spread},
        )

    positions = await manager.get_positions() if manager is not None else []
    same_symbol_positions = sum(1 for pos in positions if str(pos.get("symbol", "")).upper() == intent.symbol.upper())
    max_per_symbol = int(signal_metadata.get("max_positions_per_symbol", 0) or 0)
    if max_per_symbol and same_symbol_positions >= max_per_symbol:
        return RiskDecision(
            False,
            "MAX_POSITIONS_PER_SYMBOL",
            {"open_positions_for_symbol": same_symbol_positions, "max_positions_per_symbol": max_per_symbol},
        )

    max_total_positions = int(signal_metadata.get("max_total_positions", 0) or 0)
    if max_total_positions and len(positions) >= max_total_positions:
        return RiskDecision(
            False,
            "MAX_TOTAL_POSITIONS",
            {"open_positions": len(positions), "max_total_positions": max_total_positions},
        )

    return RiskDecision(True, "risk policy approved", result)


# ── Tick ──────────────────────────────────────────────────────────────────────

async def _tick(
    global_mode: str,
    connector:   MT5Connector,
    executor:    VantageDemoExecutor,
    manager:     TradeManager,
    journal:     DemoTradeJournal,
    risk_state:  dict,
    allowed_strategy_id: str | None = None,
    execution_pipeline: CanonicalExecutionPipeline | None = None,
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
    strategy_names = _active_strategy_names(allowed_strategy_id)
    required_timeframes = _required_timeframes(strategy_names)

    for symbol in _ALL_SYMBOLS:
        try:
            candles: dict[str, list[dict]] = {}
            for timeframe in required_timeframes:
                candles[timeframe] = await executor.get_candles(symbol, timeframe, _CANDLE_LIMITS[timeframe])
            px   = await executor.get_price(symbol)
            fetch_fails = 0
        except Exception as exc:
            _log.warning("Fetch error %s: %s", symbol, exc)
            _emit_runtime_event("DATA_UNAVAILABLE", symbol=symbol, reason=str(exc), timeframes=sorted(required_timeframes))
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
        if len(candles.get("M15", [])) < 50:
            _log.debug("Insufficient bars %s", symbol)
            _emit_runtime_event("DATA_UNAVAILABLE", symbol=symbol, reason="INSUFFICIENT_M15_BARS", bars=len(candles.get("M15", [])))
            continue
        if "D1" in required_timeframes and len(candles.get("D1", [])) < 20:
            _emit_runtime_event("DATA_UNAVAILABLE", symbol=symbol, reason="INSUFFICIENT_D1_BARS", bars=len(candles.get("D1", [])))
            continue
        if "H1" in required_timeframes and len(candles.get("H1", [])) < 24:
            _emit_runtime_event("DATA_UNAVAILABLE", symbol=symbol, reason="INSUFFICIENT_H1_BARS", bars=len(candles.get("H1", [])))
            continue
        if "M5" in required_timeframes and len(candles.get("M5", [])) < 30:
            _emit_runtime_event("DATA_UNAVAILABLE", symbol=symbol, reason="INSUFFICIENT_M5_BARS", bars=len(candles.get("M5", [])))
            continue

        _log.info("DATA %s  bars=%d  spread=%.1fpip  price=%.5f",
                  symbol, len(candles["M15"]), spread, px["bid"])
        market[symbol] = {
            "m15": candles.get("M15", []),
            "h4": candles.get("H4", []),
            "h1": candles.get("H1", []),
            "d1": candles.get("D1", []),
            "m5": candles.get("M5", []),
            "spread": spread,
            "px": px,
        }

    risk_state["_fetch_fails"] = fetch_fails

    if not market:
        return risk_state

    # ── Phase 2: Generate signals — all strategies × their pairs ──────────
    raw_signals = []

    for strategy_name in strategy_names:
        scfg = _STRATEGY_MAP[strategy_name]
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
                "h1":     market[symbol]["h1"] if strategy_name in _NEEDS_DTM_DATA else [],
                "d1":     market[symbol]["d1"] if strategy_name in _NEEDS_DTM_DATA else [],
                "m5":     market[symbol]["m5"] if strategy_name in _NEEDS_DTM_DATA else [],
                "spread_pips": market[symbol]["spread"],
                "price": market[symbol]["px"],
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
        sl_pips  = abs(signal.metadata.get("risk_pips", 10))
        risk_pct = _normalize_risk_percent(
            getattr(signal, "risk_percent", DEFAULT_RISK_PCT),
            DEFAULT_RISK_PCT,
        )
        lots     = calculate_lots(balance, sl_pips, signal.symbol, risk_pct=risk_pct)
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

        if execution_pipeline is not None:
            intent = ExecutionIntent(
                intent_id=f"{signal.strategy_name}:{signal.symbol}:{_signal_timestamp_text(signal.timestamp)}",
                strategy_id=signal.strategy_name,
                symbol=signal.symbol,
                side=signal.action,
                quantity=lots,
                stop_loss=signal.stop_loss,
                take_profit=signal.take_profit,
                metadata={"signal": signal, "spread": spread, "execution_mode": exec_mode},
            )
            result = await execution_pipeline.submit(intent)
            if result.status == "REJECTED":
                reason = str(result.details.get("reason", "risk gate rejected"))
                _log.info("SKIP %s/%s — %s", signal.strategy_name, signal.symbol, reason)
                continue
            mark_used = getattr(get_strategy(signal.strategy_name), "mark_signal_used", None)
            if callable(mark_used):
                mark_used(signal)
            order = dict(result.details)
            if exec_mode == "shadow":
                _shadow.track(signal, reason=f"shadow:{signal.strategy_name}")
                _jdb.record_signal(signal, router_result="PASS", breaker_result="PASS",
                                   portfolio_result="PASS", execution_result="SHADOW",
                                   position_size=lots)
                journal.log_open(signal, order, lots, spread)
                _portmgr.record_trade(signal)
                continue
            journal.log_open(signal, order, lots, spread)
            _jdb.record_signal(signal, router_result="PASS", breaker_result="PASS",
                               portfolio_result="PASS", execution_result="OPEN",
                               broker_order_id=result.reference, position_size=lots)
            _portmgr.record_trade(signal)
            _breaker.record_trade(signal.strategy_name, won=True)
            risk_state["open_positions"] = risk_state.get("open_positions", 0) + 1
            continue

        # Compatibility-only direct path for legacy unit fixtures. Canonical
        # runtime startup always supplies execution_pipeline.
        limit = check_limits(risk_state)
        if not limit["approved"]:
            _log.info("SKIP %s/%s — %s", signal.strategy_name, signal.symbol, limit["reason"])
            continue

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

async def run(
    mode: str,
    interval: int,
    strategy_id: str | None = None,
    execution_pipeline: CanonicalExecutionPipeline | None = None,
    runtime_components: dict[str, object] | None = None,
) -> None:
    if execution_pipeline is None:
        raise RuntimeError("canonical execution pipeline is required")
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
    if runtime_components is not None:
        runtime_components["manager"] = manager
        runtime_components["risk_state"] = risk_state

    try:
        while True:
            try:
                risk_state = await _tick(
                    mode,
                    connector,
                    executor,
                    manager,
                    journal,
                    risk_state,
                    allowed_strategy_id=strategy_id,
                    execution_pipeline=execution_pipeline,
                )
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
    parser.add_argument("--strategy-package", default=os.environ.get("APPROVED_STRATEGY_PACKAGE", ""),
                        help="Path to approved strategy package for demo execution")
    parser.add_argument("--strategy-id", default=os.environ.get("RUNNER_STRATEGY_ID", ""),
                        help="Canonical strategy ID; defaults to package metadata")
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

    package_path = _resolve_strategy_package(args)
    if not package_path or not Path(package_path).is_file():
        print("ERROR: canonical strategy-package/v2 archive is required for runtime startup")
        sys.exit(1)
    strategy_id = (args.strategy_id or package_strategy_id(package_path)).strip()
    authority = RuntimeAuthority(
        root=_ROOT,
        package_path=package_path,
        verifying_public_key=os.environ.get("SVOS_PACKAGE_VERIFYING_PUBLIC_KEY", ""),
        expected_strategy_id=strategy_id or None,
        broker_adapter="vantage-demo",
        risk_enforcer="demo-risk-firewall",
    )

    runtime_parts: dict[str, object] = {}

    class _PortfolioRiskGate:
        async def evaluate(self, _intent: ExecutionIntent) -> RiskDecision:
            state = runtime_parts.get("risk_state")
            manager = runtime_parts.get("manager")
            return await evaluate_execution_intent(
                _intent,
                risk_state=state if isinstance(state, dict) else None,
                manager=manager if isinstance(manager, TradeManager) else None,
            )

    async def _execute(intent: ExecutionIntent) -> AdapterResult:
        if intent.metadata.get("execution_mode", mode) == "shadow":
            return AdapterResult(
                "SIMULATED",
                reference=f"virtual:{intent.intent_id}",
                details={"order_id": "SHADOW", "simulated": True},
            )
        manager = runtime_parts.get("manager")
        if not isinstance(manager, TradeManager):
            raise RuntimeError("demo trade manager is unavailable")
        signal = intent.metadata["signal"]
        order = await manager.open_position(signal, intent.quantity)
        return AdapterResult("FILLED", str(order.get("order_id", "")), order)

    def _pipeline_factory(_context: RuntimeContext) -> CanonicalExecutionPipeline:
        pipeline_mode = ExecutionMode.VIRTUAL_DEMO if mode == "shadow" else ExecutionMode.DEMO
        adapter = VirtualDemoExecutionAdapter(_execute) if mode == "shadow" else DemoExecutionAdapter(_execute)
        return CanonicalExecutionPipeline(
            mode=pipeline_mode,
            risk_gate=_PortfolioRiskGate(),
            adapter=adapter,
            event_sink=lambda event: append_jsonl(
                _ROOT / "data" / "production" / "runtime" / "execution-events.jsonl",
                event.to_dict(),
            ),
        )

    async def _owned_runtime(pipeline: CanonicalExecutionPipeline) -> None:
        context = authority.snapshot()
        identity = validate_strategy_identity(
            root=_ROOT,
            package_path=package_path,
            runner_strategy_id=context.strategy_id,
        )
        identity.require_valid()
        # Objects are populated by run before the first submitted intent.
        await run(mode, args.interval, identity.strategy_id, pipeline, runtime_parts)

    try:
        asyncio.run(authority.run_pipeline(_pipeline_factory, _owned_runtime))
    except (PermissionError, ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
