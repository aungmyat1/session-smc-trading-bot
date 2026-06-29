from __future__ import annotations

from pathlib import Path
from typing import Any

from core.strategy_registry import list_catalog_strategies
from svos.governance.service import GovernanceService
from svos.lifecycle.manager import StrategyLifecycleManager
from svos.registry.service import StrategyRegistryService
from svos.reports.service import StandardizedReportService


class SVOSPlatform:
    """Unified operational layer over existing research, validation, and governance modules."""

    def __init__(
        self,
        *,
        root: Path | str,
        catalog_path: Path | str | None = None,
        lifecycle: StrategyLifecycleManager | None = None,
        registry: StrategyRegistryService | None = None,
        reports: StandardizedReportService | None = None,
        governance: GovernanceService | None = None,
    ) -> None:
        self.root = Path(root)
        self.catalog_path = Path(catalog_path) if catalog_path is not None else self.root / "config" / "strategy_catalog.yaml"
        self.lifecycle = lifecycle or StrategyLifecycleManager()
        self.registry = registry or StrategyRegistryService(root=self.root, catalog_path=self.catalog_path, lifecycle=self.lifecycle)
        self.reports = reports or StandardizedReportService(self.root)
        self.governance = governance or GovernanceService(root=self.root, registry=self.registry, lifecycle=self.lifecycle)

    def bootstrap(self) -> dict[str, Any]:
        strategies = []
        for name in list_catalog_strategies(self.catalog_path):
            strategies.append(self.registry.ensure_strategy(name).to_dict())
        return {"strategy_count": len(strategies), "strategies": strategies}

    def record_report_evidence(
        self,
        *,
        strategy: str,
        stage: str,
        service: str,
        report_type: str,
        artifact_path: Path | str,
        status: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        report = self.reports.register_artifact(
            strategy=strategy,
            stage=stage,
            service=service,
            report_type=report_type,
            artifact_path=artifact_path,
            status=status,
            metadata=metadata,
        )
        evidence = self.registry.record_evidence(
            strategy,
            stage=stage,
            service=service,
            report_type=report_type,
            artifact_path=report["artifact_path"],
            artifact_hash=report["artifact_hash"],
            status=status,
            metadata={"report_id": report["report_id"], **(metadata or {})},
        )
        return {"report": report, "evidence": evidence.to_dict()}

    def audited_transition(
        self,
        strategy: str,
        *,
        to_stage: str,
        actor: str = "system",
        reason: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        transition = self.governance.transition(
            strategy,
            to_stage=to_stage,
            actor=actor,
            reason=reason,
            metadata=metadata,
        )
        return transition.to_dict()

    def approve_transition(
        self,
        strategy: str,
        *,
        to_stage: str,
        approver: str,
        reason: str,
    ) -> dict[str, Any]:
        return self.governance.record_approval(
            strategy,
            to_stage=to_stage,
            approver=approver,
            reason=reason,
        ).to_dict()

    def strategy_summary(self, strategy: str) -> dict[str, Any]:
        record = self.registry.ensure_strategy(strategy)
        return {
            "record": record.to_dict(),
            "versions": self.registry.versions(strategy),
            "transitions": self.registry.transitions(strategy),
            "evidence": self.registry.evidence(strategy),
            "gate_decisions": self.governance.decisions(strategy),
            "approvals": self.governance.approvals(strategy),
        }
