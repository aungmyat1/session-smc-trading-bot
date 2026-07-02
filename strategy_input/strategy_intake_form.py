from __future__ import annotations

from typing import Any

from strategy_input.strategy_validator import StrategyValidationResult, validate_strategy


INTAKE_FIELDS = (
    "strategy_id",
    "version",
    "pair",
    "session",
    "bias",
    "entry",
    "risk_pct",
    "reward_risk",
    "max_trades_per_day",
    "stop_loss_required",
)


def submit_strategy_intake(form: dict[str, Any]) -> StrategyValidationResult:
    """Translate a UI/CLI form into the platform's schema validation path."""
    payload = {name: form[name] for name in INTAKE_FIELDS if name in form}
    return validate_strategy(payload)
