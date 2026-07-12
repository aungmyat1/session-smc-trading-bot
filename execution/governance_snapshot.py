"""Read-only audit projection of SVOS governance/registry state.

`GovernanceSnapshot` is a pure data container consumed by
`execution/governance_guard.py` for audit-metadata enrichment only. It must
never participate in ALLOW/DENY/WARN branching — the sole deployment
authority remains `core.strategy_registry.can_deploy_strategy`.

Deliberately excluded fields: `deployment_status`, `environment`, or any
gating/approval-flag concept. Those are runtime/call-time inputs, not
snapshot state, and including them here previously caused the guard to fail
closed on data that was never decision-relevant. Do not re-add them.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GovernanceSnapshot:
    strategy_name: str
    latest_version: str | None
    evidence_count: int
    decision_count: int
    approval_count: int
    latest_approval: dict | None
