"""Transactional PostgreSQL metadata repository for immutable reports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import Artifact, ArtifactBinding, ReportRecord
from svos.adapters.artifacts import StoredArtifact


REPORT_STATUSES = {"PASS", "FAIL", "BLOCKED", "IN_PROGRESS", "NOT_RUN", "INVALIDATED"}
TRUST_VALUES = {"QUALIFYING_REAL", "SYNTHETIC", "LEGACY_IMPORTED", "INVALIDATED"}


@dataclass(frozen=True, slots=True)
class ReportRegistration:
    report_id: str
    strategy_id: UUID
    version_id: UUID
    stage: str
    report_type: str
    status: str
    trust: str
    schema_version: str
    generator_version: str
    json_artifact: StoredArtifact
    markdown_artifact: StoredArtifact | None = None
    run_id: UUID | None = None
    actor: str = "system"


class PostgresEvidenceRepository:
    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self.session_factory = session_factory

    def register_report(self, registration: ReportRegistration) -> UUID:
        if registration.status not in REPORT_STATUSES:
            raise ValueError(f"unsupported report status: {registration.status}")
        if registration.trust not in TRUST_VALUES:
            raise ValueError(f"unsupported evidence trust: {registration.trust}")
        with self.session_factory() as session:
            with session.begin():
                existing = session.scalar(
                    select(ReportRecord).where(ReportRecord.report_id == registration.report_id)
                )
                if existing is not None:
                    return cast(UUID, existing.id)
                json_artifact = self._artifact(session, registration.strategy_id, registration.stage, registration.report_type, registration.json_artifact, "application/json", registration)
                markdown_artifact = None
                if registration.markdown_artifact is not None:
                    markdown_artifact = self._artifact(
                        session,
                        registration.strategy_id,
                        registration.stage,
                        registration.report_type,
                        registration.markdown_artifact,
                        "text/markdown",
                        registration,
                    )
                report = ReportRecord(
                    report_id=registration.report_id,
                    strategy_id=registration.strategy_id,
                    version_id=registration.version_id,
                    run_id=registration.run_id,
                    stage=registration.stage,
                    report_type=registration.report_type,
                    status=registration.status,
                    trust=registration.trust,
                    json_artifact_id=json_artifact.id,
                    markdown_artifact_id=markdown_artifact.id if markdown_artifact else None,
                    schema_version=registration.schema_version,
                    generator_version=registration.generator_version,
                )
                session.add(report)
                session.flush()
                return cast(UUID, report.id)

    def _artifact(
        self,
        session: Session,
        strategy_id: UUID,
        stage: str,
        report_type: str,
        stored: StoredArtifact,
        media_type: str,
        registration: ReportRegistration,
    ) -> Artifact:
        if len(stored.sha256) != 64 or stored.path.name != stored.sha256:
            raise ValueError("artifact is not a valid SHA-256 content address")
        artifact = Artifact(
            strategy_id=strategy_id,
            stage=stage,
            report_type=report_type,
            uri=str(stored.path),
            sha256=stored.sha256,
            media_type=media_type,
            size_bytes=stored.size_bytes,
            schema_version=registration.schema_version,
            recorded_by=registration.actor,
        )
        session.add(artifact)
        session.flush()
        return artifact

    def bind_evidence(
        self,
        *,
        strategy_id: UUID,
        version_id: UUID,
        stage: str,
        artifact_sha256: str,
        trust: str = "QUALIFYING_REAL",
    ) -> UUID:
        """Create an ArtifactBinding for a previously stored artifact.

        Returns the binding UUID, which can be passed as evidence_ids to
        PostgresControlPlane.commit_transition().
        """
        if trust not in TRUST_VALUES:
            raise ValueError(f"unsupported evidence trust: {trust}")
        with self.session_factory() as session:
            with session.begin():
                artifact = session.scalar(
                    select(Artifact).where(
                        Artifact.sha256 == artifact_sha256,
                        Artifact.strategy_id == strategy_id,
                    )
                )
                if artifact is None:
                    raise ValueError(f"artifact not found: sha256={artifact_sha256[:16]}… strategy={strategy_id}")
                binding = ArtifactBinding(
                    strategy_id=strategy_id,
                    version_id=version_id,
                    stage=stage,
                    artifact_id=artifact.id,
                    status="active",
                    trust=trust,
                )
                session.add(binding)
                session.flush()
                return cast(UUID, binding.id)
