"""
Strategy lifecycle state model.

States (in promotion order):
    research_qualified → verification_ready → execution_qualified →
    risk_qualified → demo_approved → demo_live → production_candidate →
    production_approved → production_live

Terminal / recovery states:
    suspended, rollback, revalidation_required

Every transition requires an evidence artifact dict with at minimum:
    {"evidence_type": str, "description": str, "timestamp": str}

Transitions are explicit and fail-closed: any unlisted transition raises
LifecycleTransitionError.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)

_UTC = timezone.utc


class LifecycleState(str, Enum):
    # Research / validation track
    RESEARCH_QUALIFIED = "research_qualified"
    VERIFICATION_READY = "verification_ready"
    EXECUTION_QUALIFIED = "execution_qualified"
    RISK_QUALIFIED = "risk_qualified"
    DEMO_APPROVED = "demo_approved"
    DEMO_LIVE = "demo_live"
    PRODUCTION_CANDIDATE = "production_candidate"
    PRODUCTION_APPROVED = "production_approved"
    PRODUCTION_LIVE = "production_live"
    # Terminal / recovery
    SUSPENDED = "suspended"
    ROLLBACK = "rollback"
    REVALIDATION_REQUIRED = "revalidation_required"


# Explicit allowed forward transitions.
# Any (from, to) pair NOT in this set is rejected.
_ALLOWED_TRANSITIONS: set[tuple[LifecycleState, LifecycleState]] = {
    # Happy path
    (LifecycleState.RESEARCH_QUALIFIED,   LifecycleState.VERIFICATION_READY),
    (LifecycleState.VERIFICATION_READY,   LifecycleState.EXECUTION_QUALIFIED),
    (LifecycleState.EXECUTION_QUALIFIED,  LifecycleState.RISK_QUALIFIED),
    (LifecycleState.RISK_QUALIFIED,       LifecycleState.DEMO_APPROVED),
    (LifecycleState.DEMO_APPROVED,        LifecycleState.DEMO_LIVE),
    (LifecycleState.DEMO_LIVE,            LifecycleState.PRODUCTION_CANDIDATE),
    (LifecycleState.PRODUCTION_CANDIDATE, LifecycleState.PRODUCTION_APPROVED),
    (LifecycleState.PRODUCTION_APPROVED,  LifecycleState.PRODUCTION_LIVE),
    # Suspend from any active state
    (LifecycleState.DEMO_LIVE,            LifecycleState.SUSPENDED),
    (LifecycleState.PRODUCTION_LIVE,      LifecycleState.SUSPENDED),
    (LifecycleState.PRODUCTION_APPROVED,  LifecycleState.SUSPENDED),
    # Rollback
    (LifecycleState.DEMO_LIVE,            LifecycleState.ROLLBACK),
    (LifecycleState.PRODUCTION_LIVE,      LifecycleState.ROLLBACK),
    # Revalidation required — from any non-terminal state
    (LifecycleState.RESEARCH_QUALIFIED,   LifecycleState.REVALIDATION_REQUIRED),
    (LifecycleState.VERIFICATION_READY,   LifecycleState.REVALIDATION_REQUIRED),
    (LifecycleState.EXECUTION_QUALIFIED,  LifecycleState.REVALIDATION_REQUIRED),
    (LifecycleState.RISK_QUALIFIED,       LifecycleState.REVALIDATION_REQUIRED),
    (LifecycleState.DEMO_APPROVED,        LifecycleState.REVALIDATION_REQUIRED),
    (LifecycleState.DEMO_LIVE,            LifecycleState.REVALIDATION_REQUIRED),
    (LifecycleState.PRODUCTION_CANDIDATE, LifecycleState.REVALIDATION_REQUIRED),
    (LifecycleState.PRODUCTION_LIVE,      LifecycleState.REVALIDATION_REQUIRED),
    # Re-enter research after revalidation
    (LifecycleState.REVALIDATION_REQUIRED, LifecycleState.RESEARCH_QUALIFIED),
}

# Evidence type required per target state
_REQUIRED_EVIDENCE: dict[LifecycleState, str] = {
    LifecycleState.VERIFICATION_READY:   "backtest_report",
    LifecycleState.EXECUTION_QUALIFIED:  "execution_qualification_report",
    LifecycleState.RISK_QUALIFIED:       "risk_qualification_report",
    LifecycleState.DEMO_APPROVED:        "demo_approval_sign_off",
    LifecycleState.DEMO_LIVE:            "demo_start_confirmation",
    LifecycleState.PRODUCTION_CANDIDATE: "demo_completion_report",
    LifecycleState.PRODUCTION_APPROVED:  "production_approval_sign_off",
    LifecycleState.PRODUCTION_LIVE:      "production_start_confirmation",
    LifecycleState.SUSPENDED:            "suspension_reason",
    LifecycleState.ROLLBACK:             "rollback_reason",
    LifecycleState.REVALIDATION_REQUIRED: "revalidation_trigger",
}


class LifecycleTransitionError(Exception):
    """Raised when a state transition is not permitted."""


@dataclass
class TransitionRecord:
    from_state: LifecycleState
    to_state: LifecycleState
    timestamp: str
    evidence: dict
    actor: str = "system"


@dataclass
class StrategyLifecycle:
    """
    Lifecycle state machine for a single strategy.

    Usage::
        lc = StrategyLifecycle(strategy_id="ST-A2",
                               state=LifecycleState.RESEARCH_QUALIFIED)
        lc.transition(
            LifecycleState.VERIFICATION_READY,
            evidence={"evidence_type": "backtest_report",
                      "description": "ST-A2 PF_2x=1.025 n=169 PASS",
                      "timestamp": "2026-06-21T10:04:58Z"},
            actor="backtest_runner",
        )
    """

    strategy_id: str
    state: LifecycleState = LifecycleState.RESEARCH_QUALIFIED
    history: list[TransitionRecord] = field(default_factory=list)
    created_at: str = field(
        default_factory=lambda: datetime.now(_UTC).isoformat()
    )

    def transition(
        self,
        new_state: LifecycleState,
        evidence: dict,
        actor: str = "system",
    ) -> None:
        """
        Attempt a state transition.

        Args:
            new_state: Target lifecycle state.
            evidence: Artifact dict. Must contain 'evidence_type' key matching
                      the requirement for the target state (when one exists).
            actor: Who/what initiated the transition.

        Raises:
            LifecycleTransitionError: If transition not allowed or evidence missing.
        """
        pair = (self.state, new_state)
        if pair not in _ALLOWED_TRANSITIONS:
            raise LifecycleTransitionError(
                f"[{self.strategy_id}] Transition {self.state!r} → {new_state!r} "
                "is not in the allowed transition set."
            )

        required = _REQUIRED_EVIDENCE.get(new_state)
        if required and evidence.get("evidence_type") != required:
            raise LifecycleTransitionError(
                f"[{self.strategy_id}] Transition to {new_state!r} requires "
                f"evidence_type='{required}', got '{evidence.get('evidence_type')}'."
            )

        record = TransitionRecord(
            from_state=self.state,
            to_state=new_state,
            timestamp=datetime.now(_UTC).isoformat(),
            evidence=evidence,
            actor=actor,
        )
        self.history.append(record)
        old = self.state
        self.state = new_state
        logger.info(
            "[%s] Lifecycle: %s → %s (actor=%s)",
            self.strategy_id, old.value, new_state.value, actor,
        )

    def to_dict(self) -> dict:
        return {
            "strategy_id": self.strategy_id,
            "state": self.state.value,
            "created_at": self.created_at,
            "history": [
                {
                    "from_state": r.from_state.value,
                    "to_state": r.to_state.value,
                    "timestamp": r.timestamp,
                    "evidence": r.evidence,
                    "actor": r.actor,
                }
                for r in self.history
            ],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "StrategyLifecycle":
        lc = cls(
            strategy_id=d["strategy_id"],
            state=LifecycleState(d["state"]),
            created_at=d.get("created_at", ""),
        )
        for r in d.get("history", []):
            lc.history.append(
                TransitionRecord(
                    from_state=LifecycleState(r["from_state"]),
                    to_state=LifecycleState(r["to_state"]),
                    timestamp=r["timestamp"],
                    evidence=r["evidence"],
                    actor=r.get("actor", "system"),
                )
            )
        return lc
