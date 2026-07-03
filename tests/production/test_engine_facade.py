from production.engine import (
    ACTIVE_RUNTIME_MODULES,
    DeploymentImportService,
    ExecutionGuardResult,
    ExecutionStateStore,
    GovernanceDecision,
    ImportedDeploymentPackage,
    MANAGED_POSITION_MAGIC,
    PreflightVerificationResult,
    ProductionPreflightVerifier,
    StrategyExecutionGuard,
    TradeManager,
    TradingPermissionService,
    runtime_module_inventory,
    RuntimeAuthority,
    LEGACY_RUNTIME_ENTRYPOINTS,
)
from execution.control_plane import TradingPermissionService as LegacyTradingPermissionService
from execution.execution_state import ExecutionStateStore as LegacyExecutionStateStore
from execution.governance_guard import (
    ExecutionGuardResult as LegacyExecutionGuardResult,
    GovernanceDecision as LegacyGovernanceDecision,
    StrategyExecutionGuard as LegacyStrategyExecutionGuard,
)
from execution.trade_manager import TradeManager as LegacyTradeManager, _MAGIC as LegacyManagedPositionMagic


def test_engine_facade_reexports_runtime_services() -> None:
    assert ExecutionStateStore is LegacyExecutionStateStore
    assert TradingPermissionService is LegacyTradingPermissionService
    assert StrategyExecutionGuard is LegacyStrategyExecutionGuard
    assert GovernanceDecision is LegacyGovernanceDecision
    assert ExecutionGuardResult is LegacyExecutionGuardResult
    assert TradeManager is LegacyTradeManager
    assert MANAGED_POSITION_MAGIC == LegacyManagedPositionMagic


def test_engine_runtime_inventory_exposes_execution_modules() -> None:
    inventory = runtime_module_inventory()
    assert inventory == ACTIVE_RUNTIME_MODULES
    assert "execution.control_plane" in inventory
    assert "execution.execution_state" in inventory


def test_engine_facade_exports_deployment_import_surface() -> None:
    assert DeploymentImportService.__name__ == "DeploymentImportService"
    assert ImportedDeploymentPackage.__name__ == "ImportedDeploymentPackage"
    assert ProductionPreflightVerifier.__name__ == "ProductionPreflightVerifier"
    assert PreflightVerificationResult.__name__ == "PreflightVerificationResult"


def test_engine_facade_exposes_single_runtime_authority_and_legacy_inventory() -> None:
    assert RuntimeAuthority.__name__ == "RuntimeAuthority"
    assert "production.engine.runtime" in runtime_module_inventory()
    assert "bot.py" in LEGACY_RUNTIME_ENTRYPOINTS
    assert "scripts/run_st_a2_demo.py" in LEGACY_RUNTIME_ENTRYPOINTS
    assert "scripts/run_d2_e3_demo.py" in LEGACY_RUNTIME_ENTRYPOINTS
