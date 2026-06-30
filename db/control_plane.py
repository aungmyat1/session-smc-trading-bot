"""Transactional PostgreSQL lifecycle persistence.

Policy evaluation belongs to the SVOS application layer. This repository owns
the indivisible commit of a permitted decision, transition, stage revision,
and outbox event. It never falls back to YAML or JSONL.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import (ArtifactBinding, GateDecision, Outbox, StageState,
                       StageTransition, StrategyEntity)
from svos.lifecycle.manager import StrategyLifecycleManager


class ControlPlaneError(RuntimeError):
    """Base error for a rejected control-plane commit."""


class ControlPlaneConflict(ControlPlaneError):
    """The caller evaluated a stale stage revision."""


class ControlPlaneEvidenceError(ControlPlaneError):
    """Evidence is absent, stale, invalidated, or non-qualifying."""


@dataclass(frozen=True, slots=True)
class TransitionCommand:
    strategy_slug: str
    version_id: UUID
    from_stage: str
    to_stage: str
    expected_revision: int
    actor: str
    reason: str
    policy_version: str
    evidence_ids: tuple[UUID, ...] = ()


@dataclass(frozen=True, slots=True)
class CommittedTransition:
    decision_id: UUID
    transition_id: UUID
    strategy_id: UUID
    from_revision: int
    to_revision: int


class PostgresControlPlane:
    """Fail-closed transactional lifecycle repository."""

    _NO_EVIDENCE_SOURCES = {"DRAFT", "REFINEMENT", "REVALIDATION"}

    def __init__(
        self,
        session_factory: Callable[[], Session],
        *,
        lifecycle: StrategyLifecycleManager | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.lifecycle = lifecycle or StrategyLifecycleManager()

    def commit_transition(self, command: TransitionCommand) -> CommittedTransition:
        if (
            not command.actor.strip()
            or not command.reason.strip()
            or not command.policy_version.strip()
        ):
            raise ControlPlaneError("actor, reason, and policy_version are required")
        source = self.lifecycle.normalize_stage(command.from_stage)
        target = self.lifecycle.normalize_stage(command.to_stage)
        self.lifecycle.validate_transition(source, target)

        with self.session_factory() as session:
            with session.begin():
                strategy = session.scalar(
                    select(StrategyEntity).where(
                        StrategyEntity.slug == command.strategy_slug
                    )
                )
                if strategy is None:
                    raise ControlPlaneError(
                        f"unknown strategy: {command.strategy_slug}"
                    )
                state = session.scalar(
                    select(StageState)
                    .where(StageState.strategy_id == strategy.id)
                    .with_for_update()
                )
                if state is None:
                    raise ControlPlaneError(
                        f"missing stage state: {command.strategy_slug}"
                    )
                if (
                    state.opt_lock != command.expected_revision
                    or state.current_stage != source.value
                ):
                    raise ControlPlaneConflict(
                        f"stale lifecycle state: expected {source.value}@{command.expected_revision}, "
                        f"found {state.current_stage}@{state.opt_lock}"
                    )
                if state.current_version_id != command.version_id:
                    raise ControlPlaneConflict(
                        "strategy version changed after gate evaluation"
                    )

                self._validate_evidence(
                    session, cast(UUID, strategy.id), command, source.value
                )

                decision = GateDecision(
                    strategy_id=strategy.id,
                    version_id=command.version_id,
                    from_stage=source.value,
                    to_stage=target.value,
                    allowed=True,
                    actor=command.actor,
                    reason=command.reason,
                    blockers=[],
                    evidence_ids=[str(item) for item in command.evidence_ids],
                    policy_version=command.policy_version,
                )
                session.add(decision)
                session.flush()

                next_revision = state.opt_lock + 1
                transition = StageTransition(
                    strategy_id=strategy.id,
                    version_id=command.version_id,
                    gate_decision_id=decision.id,
                    from_stage=source.value,
                    to_stage=target.value,
                    from_revision=state.opt_lock,
                    to_revision=next_revision,
                    actor=command.actor,
                    reason=command.reason,
                )
                state.current_stage = target.value  # type: ignore[assignment]
                state.opt_lock = next_revision  # type: ignore[assignment]
                state.updated_by = command.actor  # type: ignore[assignment]
                outbox = Outbox(
                    event_type="stage_transition",
                    strategy_id=strategy.id,
                    payload={
                        "decision_id": str(decision.id),
                        "from_stage": source.value,
                        "to_stage": target.value,
                        "from_revision": command.expected_revision,
                        "to_revision": next_revision,
                        "actor": command.actor,
                    },
                )
                session.add_all([transition, outbox])
                session.flush()
                result = CommittedTransition(
                    decision_id=cast(UUID, decision.id),
                    transition_id=cast(UUID, transition.id),
                    strategy_id=cast(UUID, strategy.id),
                    from_revision=command.expected_revision,
                    to_revision=int(next_revision),
                )
            return result

    def _validate_evidence(
        self,
        session: Session,
        strategy_id: UUID,
        command: TransitionCommand,
        source_stage: str,
    ) -> None:
        if source_stage in self._NO_EVIDENCE_SOURCES:
            return
        if not command.evidence_ids:
            raise ControlPlaneEvidenceError(
                f"qualifying evidence is required for {source_stage}"
            )
        bindings: Sequence[ArtifactBinding] = session.scalars(
            select(ArtifactBinding).where(ArtifactBinding.id.in_(command.evidence_ids))
        ).all()
        valid_ids = {
            item.id
            for item in bindings
            if item.strategy_id == strategy_id
            and item.version_id == command.version_id
            and item.stage == source_stage
            and item.status == "active"
            and item.trust == "QUALIFYING_REAL"
            and item.invalidated_at is None
        }
        missing = set(command.evidence_ids) - valid_ids
        if missing:
            raise ControlPlaneEvidenceError(
                "evidence must be current QUALIFYING_REAL evidence for the strategy version and source stage"
            )
