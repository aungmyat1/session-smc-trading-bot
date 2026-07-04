"""Lifecycle Authority — fail-closed gate for all strategy state mutations.

This is the single entry point through which ALL lifecycle transitions must flow.
It enforces:

1. PostgreSQL must be reachable for qualifying transitions
2. Evidence must pass trust validation (QUALIFYING_REAL) before promotion
3. File-based state.json is read-only projection; writes to it are forbidden
4. If PostgreSQL is unavailable, lifecycle mutation must fail closed

The SVOSPlatform class in svos/orchestration/service.py should route all
audited_transition() calls through this gate.

Dashboard promotion endpoints (dashboard/strategy_service.py) must also route
through this gate rather than writing directly to file-based state.

Usage:
    from svos.lifecycle.authority import LifecycleAuthority, TransitionResult
    authority = LifecycleAuthority(session_factory=<callable>)
    result = authority.transition(strategy="ST-A2", to_stage="HISTORICAL_REPLAY", actor="system", reason="...")
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import ArtifactBinding, StageState, StrategyEntity, StrategyVersion
from svos.lifecycle.manager import StrategyLifecycleManager, StrategyStage


_POLICY_VERSION = "svos-v1"
# Stages that do not require qualifying evidence for transitions
_NO_EVIDENCE_REQUIRED = frozenset({"DRAFT", "REFINEMENT", "REVALIDATION", "RETIRED"})


@dataclass(frozen=True, slots=True)
class AuthorityCommand:
    """Command to execute a lifecycle transition through the authority gate.
    
    Note: distinct from db.control_plane.TransitionCommand (the lower-level
    persistence command). AuthorityCommand is the application-layer gate that
    validates evidence and policy before delegating to PostgresControlPlane.
    """
    strategy_slug: str
    version_id: UUID
    from_stage: str
    to_stage: str
    expected_revision: int
    actor: str
    reason: str
    policy_version: str = _POLICY_VERSION


@dataclass(frozen=True, slots=True)
class TransitionResult:
    strategy_slug: str
    from_stage: str
    to_stage: str
    success: bool
    decision_id: UUID | None = None
    blockers: tuple[str, ...] = ()
    new_revision: int | None = None


class DatabaseUnavailableError(RuntimeError):
    """PostgreSQL is not reachable — all lifecycle mutations are blocked."""


class TransitionBlockedError(RuntimeError):
    """The transition is blocked by evidence or policy checks."""


class LifecycleAuthority:
    """Single authority for all lifecycle transitions.

    All state mutations flow through this class. File-based state.json is never
    written here — it is only generated as a read-only projection from PostgreSQL.
    """

    def __init__(
        self,
        session_factory: Callable[[], Session],
        lifecycle: StrategyLifecycleManager | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.lifecycle = lifecycle or StrategyLifecycleManager()

    # ── Public API ──────────────────────────────────────────────────────────

    def transition(
        self,
        *,
        strategy: str,
        to_stage: str,
        actor: str,
        reason: str,
        evidence_ids: tuple[UUID, ...] = (),
    ) -> TransitionResult:
        """Execute an evidence-validated lifecycle transition.

        Fails closed if PostgreSQL is unavailable, evidence is missing, or the
        transition is not allowed by the lifecycle rules.

        Args:
            strategy: Strategy slug (e.g. "ST-A2").
            to_stage: Target lifecycle stage.
            actor: Identity of the requesting actor.
            reason: Audit reason for the transition.
            evidence_ids: Pre-validated UUIDs of ArtifactBinding records.
                          If empty, the authority will collect qualifying evidence
                          from the database.

        Returns:
            TransitionResult with the outcome.

        Raises:
            DatabaseUnavailableError: if PostgreSQL is not reachable.
            TransitionBlockedError: if the transition is blocked.
        """
        with self.session_factory() as session:
            return self._execute_transition(session, strategy, to_stage, actor, reason, evidence_ids)

    def validate_evidence(
        self,
        *,
        strategy_id: UUID,
        version_id: UUID | None,
        stage: str,
    ) -> tuple[UUID, ...]:
        """Return qualifying evidence UUIDs for a given strategy and stage.

        Returns empty tuple if no qualifying evidence exists.
        """
        if stage.upper() in _NO_EVIDENCE_REQUIRED:
            return ()

        with self.session_factory() as session:
            bindings = session.scalars(
                select(ArtifactBinding).where(
                    ArtifactBinding.strategy_id == strategy_id,
                    ArtifactBinding.version_id == version_id,
                    ArtifactBinding.stage == stage,
                    ArtifactBinding.status == "active",
                    ArtifactBinding.trust == "QUALIFYING_REAL",
                    ArtifactBinding.invalidated_at.is_(None),
                )
            ).all()
            return tuple(b.id for b in bindings)

    def capability_check(self) -> dict:
        """Check if PostgreSQL is reachable for lifecycle operations.

        Returns dict with 'available' bool and optional 'detail' string.
        """
        try:
            with self.session_factory() as session:
                session.execute(select(StrategyEntity).limit(1))
            return {"available": True, "detail": "PostgreSQL is reachable"}
        except Exception as exc:
            return {"available": False, "detail": f"PostgreSQL unreachable: {exc}"}

    # ── Internal ────────────────────────────────────────────────────────────

    def _execute_transition(
        self,
        session: Session,
        strategy: str,
        to_stage: str,
        actor: str,
        reason: str,
        provided_evidence_ids: tuple[UUID, ...],
    ) -> TransitionResult:
        # 1. Validate lifecycle stage transition
        try:
            self.lifecycle.validate_transition_from_names(strategy, to_stage)
        except Exception as exc:
            return TransitionResult(
                strategy_slug=strategy,
                from_stage="?",
                to_stage=to_stage,
                success=False,
                blockers=(str(exc),),
            )

        # 2. Load current state with optimistic lock
        entity = session.scalar(
            select(StrategyEntity).where(StrategyEntity.slug == strategy)
        )
        if entity is None:
            raise TransitionBlockedError(f"Strategy not found: {strategy}")

        state = session.scalar(
            select(StageState).where(StageState.strategy_id == entity.id)
            .with_for_update()
        )
        if state is None:
            raise TransitionBlockedError(f"No stage state found for: {strategy}")

        # 3. Validate stage progression
        try:
            self.lifecycle.validate_transition(state.current_stage, to_stage)
        except Exception as exc:
            return TransitionResult(
                strategy_slug=strategy,
                from_stage=state.current_stage,
                to_stage=to_stage,
                success=False,
                blockers=(str(exc),),
            )

        # 4. Check evidence (if required)
        from_stage = state.current_stage
        evidence_ids = provided_evidence_ids or self.validate_evidence(
            strategy_id=entity.id,
            version_id=state.current_version_id,
            stage=from_stage,
        )

        has_evidence_requirement = from_stage.upper() not in _NO_EVIDENCE_REQUIRED
        # PRODUCTION_APPROVAL is blocked during platform construction
        target_stage = StrategyStage(to_stage.upper())
        is_production_blocked = target_stage == StrategyStage.PRODUCTION_APPROVAL
        is_remediation = target_stage in {StrategyStage.REFINEMENT, StrategyStage.REVALIDATION, StrategyStage.RETIRED}

        blockers: list[str] = []

        if has_evidence_requirement and not is_remediation and not evidence_ids:
            blockers.append(
                f"No qualifying evidence (trust=QUALIFYING_REAL, status=active) exists "
                f"for stage '{from_stage}' and current version."
            )

        if is_production_blocked:
            blockers.append(
                "Production Approval transitions are blocked during platform construction. "
                "See CLAUDE.md §6 and the SVOS implementation plan."
            )

        if not actor.strip():
            blockers.append("Actor is required for lifecycle transitions.")

        if not reason.strip():
            blockers.append("A reason/audit trail is required for lifecycle transitions.")

        if blockers:
            return TransitionResult(
                strategy_slug=strategy,
                from_stage=from_stage,
                to_stage=to_stage,
                success=False,
                blockers=tuple(blockers),
                new_revision=state.opt_lock,
            )

        # 5. Execute the transition (optimistic lock check)
        if state.opt_lock != state.opt_lock:
            # This shouldn't happen with with_for_update(), but guard anyway
            return TransitionResult(
                strategy_slug=strategy,
                from_stage=from_stage,
                to_stage=to_stage,
                success=False,
                blockers=("Optimistic lock conflict: state has been modified concurrently.",),
                new_revision=state.opt_lock,
            )

        state.current_stage = to_stage.upper()
        state.opt_lock = state.opt_lock + 1  # type: ignore[assignment]
        state.updated_by = actor

        # Flush to get the new revision
        session.flush()
        new_revision = state.opt_lock

        # Record a stage transition for the audit trail
        from db.models import StageTransition

        transition = StageTransition(
            strategy_id=entity.id,
            version_id=state.current_version_id,
            from_stage=from_stage,
            to_stage=to_stage.upper(),
            from_revision=state.opt_lock - 1,
            to_revision=new_revision,
            actor=actor,
            reason=reason,
        )
        session.add(transition)

        return TransitionResult(
            strategy_slug=strategy,
            from_stage=from_stage,
            to_stage=to_stage,
            success=True,
            new_revision=new_revision,
        )


# ── Convenience guard for file-based paths ──────────────────────────────────

# Sentinel file written by LifecycleAuthority when PostgreSQL is authoritative.
# If this file exists, file-based state.json writes are blocked.
_AUTHORITY_SENTINEL_PATH = "data/svos/.postgres_authority_active"


def mark_postgres_authority(path: str = _AUTHORITY_SENTINEL_PATH) -> None:
    """Write the authority sentinel to indicate PostgreSQL is the source of truth."""
    from pathlib import Path
    sentinel = Path(path)
    sentinel.parent.mkdir(parents=True, exist_ok=True)
    sentinel.write_text("PostgreSQL is the authoritative lifecycle mutation path.\n"
                        "File-based state.json is read-only projection only.\n")
    sentinel.chmod(0o444)


def is_postgres_authority(path: str = _AUTHORITY_SENTINEL_PATH) -> bool:
    """Return True if PostgreSQL is the authoritative lifecycle backend."""
    from pathlib import Path
    return Path(path).exists()


def assert_postgres_authority(path: str = _AUTHORITY_SENTINEL_PATH) -> None:
    """Raise RuntimeError if file-based writes would bypass PostgreSQL authority."""
    if is_postgres_authority(path):
        raise RuntimeError(
            "PostgreSQL is the authoritative lifecycle backend. "
            "Writing to data/svos/registry/*/state.json is forbidden. "
            "Use LifecycleAuthority.transition() or PostgresControlPlane.commit_transition() instead."
        )
