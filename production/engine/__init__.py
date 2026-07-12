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
    EmergencyStopRiskGate,
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
from production.engine.adapter_registry import AdapterRegistry, AdapterRegistration
from production.engine.contracts import DisabledVantageAdapter, ExecutionSignal, MarketEvent, RUNTIME_API_VERSION, SignalAction
from production.engine.coordinator import ExecutionCoordinator

__all__ = [
    "ACTIVE_RUNTIME_MODULES",
    "AdapterResult",
    "AllowAllRiskGate",
    "ActivationRecord",
    "CallbackExecutionAdapter",
    "CanonicalExecutionPipeline",
    "DemoExecutionAdapter",
    "EmergencyStopRiskGate",
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
    "AdapterRegistration", "AdapterRegistry", "DisabledVantageAdapter",
    "ExecutionSignal", "MarketEvent",
    "ExecutionCoordinator",
    "RUNTIME_API_VERSION", "SignalAction",
]
