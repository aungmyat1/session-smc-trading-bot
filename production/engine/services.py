"""Production engine service facade over the active runtime implementation."""

from execution.control_plane import TradingPermissionService
from execution.execution_state import ExecutionStateStore
from execution.governance_guard import ExecutionGuardResult, GovernanceDecision, StrategyExecutionGuard
from execution.trade_manager import TradeManager, _MAGIC as MANAGED_POSITION_MAGIC

__all__ = [
    "ExecutionGuardResult",
    "ExecutionStateStore",
    "GovernanceDecision",
    "MANAGED_POSITION_MAGIC",
    "StrategyExecutionGuard",
    "TradeManager",
    "TradingPermissionService",
]
