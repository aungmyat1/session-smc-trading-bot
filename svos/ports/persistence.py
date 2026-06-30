"""Persistence port interfaces.

These Protocol classes define the contracts for evidence recording and stage
transitions. They contain no implementation.

Concrete implementations:
  JSONL path — svos/registry/service.py (StrategyRegistryService)
  PG path    — db/control_plane.py (PostgresControlPlane) + db/evidence_repository.py
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class EvidencePort(Protocol):
    """Contract for recording qualified research evidence against a strategy version."""

    def record_evidence(
        self,
        strategy: str,
        *,
        stage: str,
        service: str,
        report_type: str,
        artifact_path: str,
        artifact_hash: str,
        status: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Record an evidence artefact and return the created evidence record.

        Returns::

            {
                "evidence_id": str,
                "strategy": str,
                "stage": str,
                "status": str,
                "artifact_hash": str,
                "recorded_at": str,     # ISO 8601
            }
        """
        ...


@runtime_checkable
class TransitionPort(Protocol):
    """Contract for committing governance-approved lifecycle transitions."""

    def commit_transition(
        self,
        strategy: str,
        *,
        to_stage: str,
        actor: str,
        reason: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Commit a stage transition after governance validation.

        Raises:
            LifecycleTransitionError: if the transition is not allowed.
            ValueError: if required evidence is missing.

        Returns::

            {
                "from_stage": str,
                "to_stage": str,
                "actor": str,
                "reason": str,
                "transition_id": str,
            }
        """
        ...
