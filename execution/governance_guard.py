from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from core.strategy_registry import can_deploy_strategy, get_strategy_manifest
from execution.governance_snapshot_provider import GovernanceSnapshotProvider
from shared.serialization import now_iso, stable_manifest_hash


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
    """Runtime deployment gate.

    The ALLOW/DENY/WARN decision is driven solely by
    ``core.strategy_registry.can_deploy_strategy`` (catalog-backed, no SVOS
    dependency). Audit metadata is enriched, best-effort, from an optional
    read-only ``GovernanceSnapshot`` — snapshot data never participates in
    the deployment decision, and a missing snapshot never changes execution
    behavior.
    """

    def __init__(
        self,
        *,
        root: Path | str,
        catalog_path: Path | str | None = None,
        snapshot_provider: GovernanceSnapshotProvider | None = None,
        shadow_mode: str = "warn",
    ) -> None:
        self.root = Path(root)
        self.catalog_path = Path(catalog_path) if catalog_path is not None else self.root / "config" / "strategy_catalog.yaml"
        self.snapshot_provider = snapshot_provider or GovernanceSnapshotProvider(root=self.root)
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

        snapshot = self.snapshot_provider.get(strategy_name)
        version = str((snapshot.latest_version if snapshot else None) or manifest.get("version", ""))
        evidence_snapshot = {
            "catalog_status": str(manifest.get("status", "")),
            "catalog_approved": bool(manifest.get("approved", False)),
            "deployment_target": str(manifest.get("deployment_target", "")),
            "evidence_count": snapshot.evidence_count if snapshot else 0,
            "decision_count": snapshot.decision_count if snapshot else 0,
            "approval_count": snapshot.approval_count if snapshot else 0,
            "latest_approval": (snapshot.latest_approval if snapshot else None) or {},
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
