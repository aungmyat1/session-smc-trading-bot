from __future__ import annotations

from pathlib import Path
from typing import Any

from svos.lifecycle.manager import (LifecycleTransitionError,
                                    StrategyLifecycleManager, StrategyStage)
from svos.registry.service import StrategyRegistryService
from svos.shared.models import ApprovalRecord, GateDecision, TransitionRecord
from svos.shared.support import (append_jsonl, now_iso, read_jsonl,
                                 stable_manifest_hash)


class GovernanceGateError(LifecycleTransitionError):
    """Raised when qualification evidence or approval blocks promotion."""


_NO_EVIDENCE_REQUIRED = {
    StrategyStage.DRAFT,
    StrategyStage.REFINEMENT,
    StrategyStage.REVALIDATION,
}
_APPROVAL_REQUIRED_TARGETS = {StrategyStage.PRODUCTION_APPROVAL}
_REMEDIATION_TARGETS = {
    StrategyStage.REFINEMENT,
    StrategyStage.REVALIDATION,
    StrategyStage.RETIRED,
}


class GovernanceService:
    """Evidence-driven control plane for all lifecycle transitions."""

    def __init__(
        self,
        *,
        root: Path | str,
        registry: StrategyRegistryService,
        lifecycle: StrategyLifecycleManager | None = None,
    ) -> None:
        self.root = Path(root)
        self.registry = registry
        self.lifecycle = lifecycle or registry.lifecycle
        self.governance_root = self.root / "data" / "svos" / "governance"

    def _decisions_path(self, strategy: str) -> Path:
        return self.governance_root / strategy / "decisions.jsonl"

    def _approvals_path(self, strategy: str) -> Path:
        return self.governance_root / strategy / "approvals.jsonl"

    def record_approval(
        self,
        strategy: str,
        *,
        to_stage: str,
        approver: str,
        reason: str,
    ) -> ApprovalRecord:
        current = self.registry.ensure_strategy(strategy)
        target = self.lifecycle.normalize_stage(to_stage)
        self.lifecycle.validate_transition(current.current_stage, target)
        if not approver.strip() or not reason.strip():
            raise ValueError("An approval requires a named approver and a reason.")
        approved_at = now_iso()
        approval = ApprovalRecord(
            approval_id=stable_manifest_hash(
                {
                    "strategy": strategy,
                    "from_stage": current.current_stage,
                    "to_stage": target.value,
                    "version": current.current_version_id,
                    "approved_at": approved_at,
                    "approver": approver,
                }
            ),
            strategy=strategy,
            from_stage=current.current_stage,
            to_stage=target.value,
            approved_at=approved_at,
            approver=approver,
            reason=reason,
            current_version_id=current.current_version_id,
        )
        append_jsonl(self._approvals_path(strategy), approval.to_dict())
        return approval

    def evaluate_transition(
        self,
        strategy: str,
        *,
        to_stage: str,
        actor: str = "system",
        reason: str = "",
    ) -> GateDecision:
        current = self.registry.ensure_strategy(strategy)
        source = self.lifecycle.normalize_stage(current.current_stage)
        target = self.lifecycle.normalize_stage(to_stage)
        self.lifecycle.validate_transition(source, target)
        blockers: list[str] = []
        qualifying: list[dict[str, Any]] = []

        if not actor.strip():
            blockers.append("A gate decision requires an actor.")
        if not reason.strip():
            blockers.append("A lifecycle transition requires an audit reason.")

        if source not in _NO_EVIDENCE_REQUIRED and target not in _REMEDIATION_TARGETS:
            qualifying = [
                item
                for item in self.registry.evidence(strategy)
                if self._same_stage(item.get("stage"), source)
                and str(item.get("status", "")).upper() == "PASS"
                and item.get("artifact_hash")
                and item.get("metadata", {}).get("current_version_id")
                == current.current_version_id
            ]
            if not qualifying:
                blockers.append(
                    f"No PASS evidence with an artifact hash exists for {source.value} and strategy version {current.latest_version}."
                )

        approval = self._matching_approval(
            strategy, source, target, current.current_version_id
        )
        if target in _APPROVAL_REQUIRED_TARGETS and approval is None:
            blockers.append(
                f"An explicit approval is required before entering {target.value}."
            )

        decided_at = now_iso()
        payload = {
            "strategy": strategy,
            "from_stage": source.value,
            "to_stage": target.value,
            "version": current.current_version_id,
            "decided_at": decided_at,
            "actor": actor,
            "allowed": not blockers,
        }
        decision = GateDecision(
            decision_id=stable_manifest_hash(payload),
            strategy=strategy,
            from_stage=source.value,
            to_stage=target.value,
            allowed=not blockers,
            decided_at=decided_at,
            actor=actor,
            reason=reason,
            evidence_ids=[str(item["evidence_id"]) for item in qualifying],
            blockers=blockers,
            approval_id=str(approval.get("approval_id", "")) if approval else "",
            current_version_id=current.current_version_id,
        )
        append_jsonl(self._decisions_path(strategy), decision.to_dict())
        return decision

    def transition(
        self,
        strategy: str,
        *,
        to_stage: str,
        actor: str = "system",
        reason: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> TransitionRecord:
        decision = self.evaluate_transition(
            strategy, to_stage=to_stage, actor=actor, reason=reason
        )
        if not decision.allowed:
            raise GovernanceGateError("; ".join(decision.blockers))
        return self.registry.transition(
            strategy,
            to_stage=decision.to_stage,
            actor=actor,
            reason=reason,
            metadata=metadata,
            governance_decision=decision,
        )

    def decisions(self, strategy: str) -> list[dict[str, Any]]:
        return read_jsonl(self._decisions_path(strategy))

    def approvals(self, strategy: str) -> list[dict[str, Any]]:
        return read_jsonl(self._approvals_path(strategy))

    def _matching_approval(
        self,
        strategy: str,
        source: StrategyStage,
        target: StrategyStage,
        version_id: str,
    ) -> dict[str, Any] | None:
        matches = [
            item
            for item in self.approvals(strategy)
            if item.get("from_stage") == source.value
            and item.get("to_stage") == target.value
            and item.get("current_version_id") == version_id
        ]
        return matches[-1] if matches else None

    def _same_stage(self, value: object, expected: StrategyStage) -> bool:
        try:
            return self.lifecycle.normalize_stage(str(value)) is expected
        except LifecycleTransitionError:
            aliases = {
                "STRATEGY_AUDIT": StrategyStage.AUDIT,
                "HISTORICAL_REPLAY": StrategyStage.HISTORICAL_REPLAY,
                "BACKTEST": StrategyStage.STATISTICAL_VALIDATION,
                "ROBUSTNESS": StrategyStage.ROBUSTNESS_VALIDATION,
                "PRODUCTION_APPROVAL": StrategyStage.PRODUCTION_APPROVAL,
            }
            return aliases.get(str(value).strip().upper()) is expected
