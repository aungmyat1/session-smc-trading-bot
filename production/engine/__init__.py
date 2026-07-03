"""Compatibility-safe production engine namespace."""

from production.activation import ActivationRecord, ProductionActivationService
from production.importer import DeploymentImportService, ImportedDeploymentPackage
from production.summary import ProductionDeploymentSummary, ProductionSummaryService
from production.verifier import PreflightVerificationResult, ProductionPreflightVerifier
from production.engine.runtime import (
    ACTIVE_RUNTIME_MODULES,
    LEGACY_RUNTIME_ENTRYPOINTS,
    RuntimeAuthority,
    RuntimeContext,
    RuntimeOwnershipError,
    RuntimeSnapshot,
    RuntimeState,
    runtime_module_inventory,
)
from production.engine.execution_pipeline import (
    AdapterResult,
    AllowAllRiskGate,
    CallbackExecutionAdapter,
    CanonicalExecutionPipeline,
    DemoExecutionAdapter,
    ExecutionIntent,
    ExecutionMode,
    NormalizedExecutionEvent,
    ReplayExecutionAdapter,
    RiskDecision,
    VirtualDemoExecutionAdapter,
)
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
    "AdapterResult",
    "AllowAllRiskGate",
    "ActivationRecord",
    "CallbackExecutionAdapter",
    "CanonicalExecutionPipeline",
    "DemoExecutionAdapter",
    "ExecutionIntent",
    "ExecutionMode",
    "LEGACY_RUNTIME_ENTRYPOINTS",
    "RuntimeAuthority",
    "RuntimeContext",
    "RuntimeOwnershipError",
    "RuntimeSnapshot",
    "RuntimeState",
    "ProductionActivationService",
    "DeploymentImportService",
    "ProductionDeploymentSummary",
    "ProductionSummaryService",
    "ExecutionGuardResult",
    "ExecutionStateStore",
    "GovernanceDecision",
    "ImportedDeploymentPackage",
    "MANAGED_POSITION_MAGIC",
    "NormalizedExecutionEvent",
    "PreflightVerificationResult",
    "ProductionPreflightVerifier",
    "ReplayExecutionAdapter",
    "RiskDecision",
    "VirtualDemoExecutionAdapter",
    "StrategyExecutionGuard",
    "TradeManager",
    "TradingPermissionService",
    "runtime_module_inventory",
]
