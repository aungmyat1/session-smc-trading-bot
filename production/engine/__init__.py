"""Compatibility-safe production engine namespace."""

from production.activation import ActivationRecord, ProductionActivationService
from production.importer import DeploymentImportService, ImportedDeploymentPackage
from production.summary import ProductionDeploymentSummary, ProductionSummaryService
from production.verifier import PreflightVerificationResult, ProductionPreflightVerifier
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
    "ActivationRecord",
    "ProductionActivationService",
    "DeploymentImportService",
    "ProductionDeploymentSummary",
    "ProductionSummaryService",
    "ExecutionGuardResult",
    "ExecutionStateStore",
    "GovernanceDecision",
    "ImportedDeploymentPackage",
    "MANAGED_POSITION_MAGIC",
    "PreflightVerificationResult",
    "ProductionPreflightVerifier",
    "StrategyExecutionGuard",
    "TradeManager",
    "TradingPermissionService",
    "runtime_module_inventory",
]
