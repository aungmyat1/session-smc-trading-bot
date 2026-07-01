"""Compatibility-safe production engine namespace."""

from production.engine.runtime import ACTIVE_RUNTIME_MODULES, runtime_module_inventory
from production.engine.services import (
    ExecutionGuardResult,
    ExecutionStateStore,
    GovernanceDecision,
    MANAGED_POSITION_MAGIC,
    StrategyExecutionGuard,
    TradeManager,
    TradingPermissionService,
)

__all__ = [
    "ACTIVE_RUNTIME_MODULES",
    "ExecutionGuardResult",
    "ExecutionStateStore",
    "GovernanceDecision",
    "MANAGED_POSITION_MAGIC",
    "StrategyExecutionGuard",
    "TradeManager",
    "TradingPermissionService",
    "runtime_module_inventory",
]
