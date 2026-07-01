from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from core.strategy_registry import can_deploy_strategy, get_strategy_manifest
from svos.governance.service import GovernanceService
from svos.registry.service import StrategyRegistryService
from svos.shared.support import now_iso, stable_manifest_hash


@dataclass(slots=True)
class GovernanceDecision:
    strategy_id: str
    strategy_version: str
    environment: str
    allowed: bool
    reason_code: str
    evidence_snapshot: dict[str, Any] = field(default_factory=dict)
    evaluated_at: str = field(default_factory=now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ExecutionGuardResult:
    allowed: bool
    decision_source: str
    reason_code: str
    audit_ref: str
    decision: GovernanceDecision

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["decision"] = self.decision.to_dict()
        return payload


class StrategyExecutionGuard:
    """Runtime deployment gate backed by the existing SVOS registry/governance data."""

    def __init__(
        self,
        *,
        root: Path | str,
        catalog_path: Path | str | None = None,
        registry: StrategyRegistryService | None = None,
        governance: GovernanceService | None = None,
        shadow_mode: str = "warn",
    ) -> None:
        self.root = Path(root)
        self.catalog_path = Path(catalog_path) if catalog_path is not None else self.root / "config" / "strategy_catalog.yaml"
        self.registry = registry or StrategyRegistryService(root=self.root, catalog_path=self.catalog_path)
        self.governance = governance or GovernanceService(root=self.root, registry=self.registry)
        self.shadow_mode = shadow_mode.strip().lower() or "warn"

    def evaluate(
        self,
        strategy_name: str,
        *,
        environment: str,
        actor: str = "runtime",
    ) -> ExecutionGuardResult:
        env = environment.strip().lower() or "shadow"
        manifest = get_strategy_manifest(strategy_name, self.catalog_path)
        if manifest is None:
            return self._result(
                strategy_name=strategy_name,
                strategy_version="",
                environment=env,
                allowed=False,
                reason_code="STRATEGY_NOT_FOUND",
                decision_source="registry",
                evidence_snapshot={},
            )

        record = self.registry.ensure_strategy(strategy_name, actor=actor, reason="runtime execution guard bootstrap")
        version = str(record.latest_version or manifest.get("version", ""))
        version_id = str(record.current_version_id)
        decisions = self.governance.decisions(strategy_name)
        approvals = self.governance.approvals(strategy_name)
        evidence = self.registry.evidence(strategy_name)
        matched_approvals = [
            item
            for item in approvals
            if str(item.get("current_version_id", "")) == version_id
        ]
        evidence_snapshot = {
            "current_stage": record.current_stage,
            "current_version_id": version_id,
            "catalog_status": str(manifest.get("status", "")),
            "catalog_approved": bool(manifest.get("approved", False)),
            "deployment_target": str(manifest.get("deployment_target", "")),
            "evidence_count": len(
                [
                    item
                    for item in evidence
                    if str(item.get("metadata", {}).get("current_version_id", "")) == version_id
                ]
            ),
            "decision_count": len(decisions),
            "approval_count": len(matched_approvals),
            "latest_approval": matched_approvals[-1] if matched_approvals else {},
        }

        permitted = can_deploy_strategy(strategy_name, target_stage=env, path=self.catalog_path)
        if env == "shadow" and self.shadow_mode == "warn":
            if permitted:
                return self._result(
                    strategy_name=strategy_name,
                    strategy_version=version,
                    environment=env,
                    allowed=True,
                    reason_code="ALLOWED",
                    decision_source="registry_governance",
                    evidence_snapshot=evidence_snapshot,
                )
            return self._result(
                strategy_name=strategy_name,
                strategy_version=version,
                environment=env,
                allowed=True,
                reason_code="WARN_SHADOW_GOVERNANCE_INCOMPLETE",
                decision_source="shadow_warning",
                evidence_snapshot=evidence_snapshot,
            )

        if not permitted:
            return self._result(
                strategy_name=strategy_name,
                strategy_version=version,
                environment=env,
                allowed=False,
                reason_code="DEPLOYMENT_NOT_APPROVED",
                decision_source="registry_governance",
                evidence_snapshot=evidence_snapshot,
            )

        return self._result(
            strategy_name=strategy_name,
            strategy_version=version,
            environment=env,
            allowed=True,
            reason_code="ALLOWED",
            decision_source="registry_governance",
            evidence_snapshot=evidence_snapshot,
        )

    def _result(
        self,
        *,
        strategy_name: str,
        strategy_version: str,
        environment: str,
        allowed: bool,
        reason_code: str,
        decision_source: str,
        evidence_snapshot: dict[str, Any],
    ) -> ExecutionGuardResult:
        decision = GovernanceDecision(
            strategy_id=strategy_name,
            strategy_version=strategy_version,
            environment=environment,
            allowed=allowed,
            reason_code=reason_code,
            evidence_snapshot=evidence_snapshot,
        )
        audit_ref = stable_manifest_hash(
            {
                "strategy": strategy_name,
                "version": strategy_version,
                "environment": environment,
                "allowed": allowed,
                "reason_code": reason_code,
                "evaluated_at": decision.evaluated_at,
            }
        )
        return ExecutionGuardResult(
            allowed=allowed,
            decision_source=decision_source,
            reason_code=reason_code,
            audit_ref=audit_ref,
            decision=decision,
        )
