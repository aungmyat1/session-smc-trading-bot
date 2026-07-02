from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError

from strategy_input.strategy_spec_schema import StrategySpec


@dataclass(frozen=True, slots=True)
class StrategyValidationResult:
    valid: bool
    spec: StrategySpec | None = None
    errors: tuple[str, ...] = field(default_factory=tuple)


def validate_strategy(value: StrategySpec | dict[str, Any]) -> StrategyValidationResult:
    """Validate intake only; this deliberately cannot approve a strategy."""
    try:
        spec = value if isinstance(value, StrategySpec) else StrategySpec.model_validate(value)
    except ValidationError as exc:
        errors = tuple(f"{'.'.join(map(str, item['loc']))}: {item['msg']}" for item in exc.errors())
        return StrategyValidationResult(valid=False, errors=errors)
    return StrategyValidationResult(valid=True, spec=spec)
