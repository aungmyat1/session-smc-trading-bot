"""Strategy Engineering Platform intake boundary."""

from strategy_input.strategy_spec_schema import StrategySpec
from strategy_input.strategy_validator import StrategyValidationResult, validate_strategy

__all__ = ["StrategySpec", "StrategyValidationResult", "validate_strategy"]
