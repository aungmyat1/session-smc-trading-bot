from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_RULES_PATH = (
    _ROOT / "execution_validation" / "config" / "validation_rules.yaml"
)


@dataclass(slots=True)
class ValidationRules:
    signal_match_minimum: float = 0.99
    maximum_slippage_pip: float = 0.5
    maximum_pf_difference: float = 0.10
    maximum_missing_orders: float = 0.01
    minimum_demo_executed_orders: int = 1
    minimum_shadow_executed_orders: int = 30
    minimum_small_live_executed_orders: int = 30
    minimum_live_executed_orders: int = 100
    risk_account_balance: float = 10_000.0
    risk_pct: float = 0.5
    max_spread_points: dict[str, float] = field(
        default_factory=lambda: {"EURUSD": 3.0, "GBPUSD": 4.0, "XAUUSD": 30.0}
    )
    minimum_lot: float = 0.01
    maximum_lot: float = 10.0
    min_stop_distance_points: int = 50
    strategy_name: str = "ST-A2"
    strategy_version: str = "2.1.3"
    rules_hash: str = "a83f92"


def load_validation_rules(path: Path | str | None = None) -> ValidationRules:
    rules_path = Path(path) if path is not None else _DEFAULT_RULES_PATH
    payload: dict[str, Any] = {}
    if rules_path.exists():
        loaded = yaml.safe_load(rules_path.read_text(encoding="utf-8")) or {}
        if isinstance(loaded, dict):
            payload = loaded
    return ValidationRules(
        signal_match_minimum=float(
            payload.get("signal_match", {}).get("minimum", 0.99)
        ),
        maximum_slippage_pip=float(payload.get("maximum_slippage_pip", 0.5)),
        maximum_pf_difference=float(payload.get("maximum_pf_difference", 0.10)),
        maximum_missing_orders=float(payload.get("maximum_missing_orders", 0.01)),
        minimum_demo_executed_orders=int(
            payload.get("minimum_demo_executed_orders", 1)
        ),
        minimum_shadow_executed_orders=int(
            payload.get("minimum_shadow_executed_orders", 30)
        ),
        minimum_small_live_executed_orders=int(
            payload.get("minimum_small_live_executed_orders", 30)
        ),
        minimum_live_executed_orders=int(
            payload.get("minimum_live_executed_orders", 100)
        ),
        risk_account_balance=float(payload.get("risk_account_balance", 10_000.0)),
        risk_pct=float(payload.get("risk_pct", 0.5)),
        max_spread_points=dict(
            payload.get("max_spread", {"EURUSD": 3.0, "GBPUSD": 4.0, "XAUUSD": 30.0})
        ),
        minimum_lot=float(payload.get("minimum_lot", 0.01)),
        maximum_lot=float(payload.get("maximum_lot", 10.0)),
        min_stop_distance_points=int(payload.get("min_stop_distance_points", 50)),
        strategy_name=str(payload.get("strategy_name", "ST-A2")),
        strategy_version=str(payload.get("strategy_version", "2.1.3")),
        rules_hash=str(payload.get("rules_hash", "a83f92")),
    )
