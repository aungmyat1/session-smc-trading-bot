"""Shared governance/registry snapshot computation.

This is SVOS (System-1) tooling: it imports SVOS registry/governance services
freely. It computes the read-only audit projection consumed downstream by:

- `scripts/export_governance_snapshot.py` (writes the loose dev-workflow file
  `artifacts/svos/strategy_snapshots.json`, read by
  `execution/governance_snapshot_provider.py`).
- `svos/deployment/service.py`'s `DeploymentStatusService.build_strategy_package`
  (embeds the per-strategy snapshot as the packaged `governance_snapshot.json`
  member, per System2 Scope 3).

Both call sites reuse this single computation so the snapshot shape and
semantics never drift between the loose-file dev path and the packaged path.
This module contains no deployment, signing, or execution-decision logic.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from svos.governance.service import GovernanceService
from svos.registry.service import StrategyRegistryService


def compute_strategy_governance_snapshot(
    registry: StrategyRegistryService,
    governance: GovernanceService,
    strategy_name: str,
    *,
    actor: str = "governance_snapshot",
    reason: str = "snapshot export",
) -> dict[str, Any]:
    """Compute the governance snapshot fields for a single strategy."""

    record = registry.ensure_strategy(strategy_name, actor=actor, reason=reason)
    version_id = str(record.current_version_id)
    decisions = governance.decisions(strategy_name)
    approvals = governance.approvals(strategy_name)
    evidence = registry.evidence(strategy_name)
    matched_approvals = [
        approval
        for approval in approvals
        if str(approval.get("current_version_id", "")) == version_id
    ]
    matched_evidence = [
        row
        for row in evidence
        if str(row.get("metadata", {}).get("current_version_id", "")) == version_id
    ]
    return {
        "latest_version": str(record.latest_version),
        "evidence_count": len(matched_evidence),
        "decision_count": len(decisions),
        "approval_count": len(matched_approvals),
        "latest_approval": matched_approvals[-1] if matched_approvals else None,
    }


def compute_all_governance_snapshots(root: Path) -> dict[str, Any]:
    """Compute the `{"strategies": {name: snapshot}}` payload for every catalog strategy."""

    registry = StrategyRegistryService(root=root)
    governance = GovernanceService(root=root, registry=registry)
    summary = registry.summary()

    strategies: dict[str, dict[str, Any]] = {}
    for item in summary.get("strategies", []):
        strategy_name = str(item.get("strategy", ""))
        if not strategy_name:
            continue
        strategies[strategy_name] = compute_strategy_governance_snapshot(
            registry, governance, strategy_name, reason="snapshot export"
        )

    return {"strategies": strategies}
