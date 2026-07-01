from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from core.base_strategy import BaseStrategy
from shared.strategy_api import Signal

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

_ROOT = Path(__file__).resolve().parents[2]
_STRATEGY_CONFIG_PATH = _ROOT / "strategy" / "session_liquidity" / "config.yaml"
_PORTFOLIO_CONFIG_PATH = _ROOT / "config" / "strategy_portfolio.yaml"
_LEGACY_CONFIG_PATH = _ROOT / "config" / "config.json"


def _read_yaml(path: Path) -> dict:
    if yaml is None or not path.exists():
        return {}
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return payload if isinstance(payload, dict) else {}


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _load_st_a2_config(runtime_config: dict | None = None, symbol: str = "") -> dict:
    config: dict = {}
    config.update(_read_yaml(_STRATEGY_CONFIG_PATH))

    legacy = _read_json(_LEGACY_CONFIG_PATH)
    session_strategy = legacy.get("session_strategy", {})
    if isinstance(session_strategy, dict):
        config.update(session_strategy)

    portfolio = _read_yaml(_PORTFOLIO_CONFIG_PATH).get("strategies", {})
    st_a2 = portfolio.get("ST-A2", {}) if isinstance(portfolio, dict) else {}
    parameters = st_a2.get("parameters", {}) if isinstance(st_a2, dict) else {}
    if isinstance(parameters, dict):
        default_parameters = parameters.get("default", {})
        if isinstance(default_parameters, dict):
            config.update(default_parameters)
        symbol_parameters = parameters.get(symbol.upper(), {})
        if isinstance(symbol_parameters, dict):
            config.update(symbol_parameters)

    if isinstance(runtime_config, dict):
        config.update(runtime_config)
    return config


def _to_core_signal(strategy_name: str, symbol: str, raw_signal: object) -> Signal:
    action = "BUY" if str(getattr(raw_signal, "side", "")).lower() == "long" else "SELL"
    return Signal(
        timestamp=datetime.now(timezone.utc).isoformat(),
        strategy_name=strategy_name,
        symbol=symbol,
        action=action,
        order_type="MARKET",
        entry_price=float(getattr(raw_signal, "entry")),
        stop_loss=float(getattr(raw_signal, "stop_loss")),
        take_profit=float(getattr(raw_signal, "take_profit")),
        risk_percent=0.25,
        confidence=1.0,
        metadata={
            "session": str(getattr(raw_signal, "session", "")),
            "risk_pips": float(getattr(raw_signal, "risk_pips", 0.0)),
            "reward_pips": float(getattr(raw_signal, "reward_pips", 0.0)),
            "rr": float(getattr(raw_signal, "rr", 0.0)),
            "reason": str(getattr(raw_signal, "reason", "")),
        },
    )


class ST2Adapter(BaseStrategy):
    @property
    def name(self) -> str:
        return "ST-A2"

    def generate_signal(self, data: dict):
        try:
            from strategy.session_liquidity.session_strategy import run_strategy
        except ImportError:
            return None

        m15 = data.get("m15", [])
        h4 = data.get("h4", [])
        symbol = data.get("symbol", "")
        if len(m15) < 50:
            return None

        config = _load_st_a2_config(data.get("config"), symbol)
        raw_signals = run_strategy(m15, h4, symbol, config)
        if not raw_signals:
            return None
        return _to_core_signal(self.name, symbol, raw_signals[-1])
