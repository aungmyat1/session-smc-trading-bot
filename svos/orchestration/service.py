from __future__ import annotations

import hashlib
import json
import os
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import UUID

from core.strategy_registry import get_strategy_manifest, list_catalog_strategies
from svos.experiments.manager import ExperimentManager, ExperimentRecord
from svos.governance.service import GovernanceService
from svos.lifecycle.manager import StrategyLifecycleManager
from svos.registry.service import StrategyRegistryService
from svos.reports.service import StandardizedReportService

if TYPE_CHECKING:
    from db.control_plane import PostgresControlPlane
    from db.evidence_repository import PostgresEvidenceRepository


_POLICY_VERSION = "svos-v1"
_PG_NO_EVIDENCE_SOURCES = frozenset({"DRAFT", "REFINEMENT", "REVALIDATION"})


class PersistenceMode(str, Enum):
    AUTO = "auto"
    LOCAL_COMPAT = "local_compat"
    AUTHORITATIVE_PG = "authoritative_pg"


def _build_pg_backends(url: str, lifecycle: StrategyLifecycleManager) -> tuple[PostgresControlPlane, PostgresEvidenceRepository]:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from db.control_plane import PostgresControlPlane
    from db.evidence_repository import PostgresEvidenceRepository
    engine = create_engine(url, pool_pre_ping=True)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    return PostgresControlPlane(sessions, lifecycle=lifecycle), PostgresEvidenceRepository(sessions)


class SVOSPlatform:
    """Unified operational layer over existing research, validation, and governance modules."""

    def __init__(
        self,
        *,
        root: Path | str,
        catalog_path: Path | str | None = None,
        lifecycle: StrategyLifecycleManager | None = None,
        registry: StrategyRegistryService | None = None,
        reports: StandardizedReportService | None = None,
        governance: GovernanceService | None = None,
        pg_control_plane: PostgresControlPlane | None = None,
        pg_evidence_repo: PostgresEvidenceRepository | None = None,
        persistence_mode: str | PersistenceMode = PersistenceMode.AUTO,
    ) -> None:
        self.root = Path(root)
        self.catalog_path = Path(catalog_path) if catalog_path is not None else self.root / "config" / "strategy_catalog.yaml"
        _lifecycle = lifecycle or StrategyLifecycleManager()
        self.lifecycle = _lifecycle
        self.registry = registry or StrategyRegistryService(root=self.root, catalog_path=self.catalog_path, lifecycle=_lifecycle)
        self.reports = reports or StandardizedReportService(self.root)
        self.governance = governance or GovernanceService(root=self.root, registry=self.registry, lifecycle=_lifecycle)

        self.persistence_mode = (
            persistence_mode
            if isinstance(persistence_mode, PersistenceMode)
            else PersistenceMode(str(persistence_mode))
        )

        # PG backends: use injected values; auto-detect from DATABASE_URL only when permitted.
        # Asyncpg (async) URLs are skipped — this layer requires a synchronous driver.
        if pg_control_plane is None and pg_evidence_repo is None and self.persistence_mode != PersistenceMode.LOCAL_COMPAT:
            _url = os.getenv("DATABASE_URL", "")
            if _url and "asyncpg" not in _url:
                try:
                    pg_control_plane, pg_evidence_repo = _build_pg_backends(_url, _lifecycle)
                except Exception as exc:
                    if self.persistence_mode == PersistenceMode.AUTHORITATIVE_PG:
                        raise RuntimeError(
                            "PostgreSQL-authoritative persistence mode is enabled, but the control-plane backends "
                            "could not be initialized from DATABASE_URL."
                        ) from exc

        if self.persistence_mode == PersistenceMode.AUTHORITATIVE_PG and (
            pg_control_plane is None or pg_evidence_repo is None
        ):
            raise RuntimeError(
                "PostgreSQL-authoritative persistence mode requires both the control-plane and evidence repositories."
            )
        self.pg_control_plane: PostgresControlPlane | None = pg_control_plane
        self.pg_evidence_repo: PostgresEvidenceRepository | None = pg_evidence_repo
        self._experiments = ExperimentManager(self.root)

    @property
    def _pg_active(self) -> bool:
        return self.pg_control_plane is not None and self.pg_evidence_repo is not None

    def persistence_status(self) -> dict[str, Any]:
        effective_mode = (
            PersistenceMode.AUTHORITATIVE_PG.value
            if self._pg_active and self.persistence_mode == PersistenceMode.AUTHORITATIVE_PG
            else (PersistenceMode.LOCAL_COMPAT.value if not self._pg_active else "pg_auto")
        )
        return {
            "configured_mode": self.persistence_mode.value,
            "effective_mode": effective_mode,
            "pg_active": self._pg_active,
            "jsonl_enabled": not self._pg_active,
            "database_url_configured": bool(os.getenv("DATABASE_URL", "").strip()),
            "authoritative": self.persistence_mode == PersistenceMode.AUTHORITATIVE_PG,
        }

    # ── bootstrap ──────────────────────────────────────────────────────────

    def bootstrap(self) -> dict[str, Any]:
        if self._pg_active:
            return self._bootstrap_pg()
        strategies = []
        for name in list_catalog_strategies(self.catalog_path):
            strategies.append(self.registry.ensure_strategy(name).to_dict())
        return {"strategy_count": len(strategies), "strategies": strategies}

    def _bootstrap_pg(self) -> dict[str, Any]:
        from sqlalchemy import select
        from db.models import StageState, StrategyEntity, StrategyVersion

        sf = self.pg_control_plane.session_factory  # type: ignore[union-attr]
        seeded: list[dict[str, Any]] = []

        for name in list_catalog_strategies(self.catalog_path):
            manifest = dict(get_strategy_manifest(name, self.catalog_path) or {})
            stage = self.lifecycle.infer_stage(manifest).value
            version = str(manifest.get("version", "0.0.0"))
            spec_hash = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()

            with sf() as session:
                with session.begin():
                    entity = session.scalar(
                        select(StrategyEntity).where(StrategyEntity.slug == name)
                    )
                    if entity is None:
                        entity = StrategyEntity(
                            name=name,
                            slug=name,
                            owner=str(manifest.get("owner", "system")),
                        )
                        session.add(entity)
                        session.flush()

                        ver = StrategyVersion(
                            strategy_id=entity.id,
                            version=version,
                            spec_hash=spec_hash,
                            rules_json=manifest,
                            created_by="bootstrap",
                        )
                        session.add(ver)
                        session.flush()

                        session.add(
                            StageState(
                                strategy_id=entity.id,
                                current_stage=stage,
                                current_version_id=ver.id,
                                opt_lock=0,
                                updated_by="bootstrap",
                            )
                        )

                    seeded.append({"strategy": name, "stage": stage})

        return {"strategy_count": len(seeded), "strategies": seeded}

    # ── evidence + transition (dispatches to JSONL or PG) ─────────────────

    def record_report_evidence(
        self,
        *,
        strategy: str,
        stage: str,
        service: str,
        report_type: str,
        artifact_path: Path | str,
        status: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if self._pg_active:
            return self._pg_record_evidence(
                strategy=strategy,
                stage=stage,
                service=service,
                report_type=report_type,
                artifact_path=artifact_path,
                status=status,
                metadata=metadata,
            )
        report = self.reports.register_artifact(
            strategy=strategy,
            stage=stage,
            service=service,
            report_type=report_type,
            artifact_path=artifact_path,
            status=status,
            metadata=metadata,
        )
        evidence = self.registry.record_evidence(
            strategy,
            stage=stage,
            service=service,
            report_type=report_type,
            artifact_path=report["artifact_path"],
            artifact_hash=report["artifact_hash"],
            status=status,
            metadata={"report_id": report["report_id"], **(metadata or {})},
        )
        return {"report": report, "evidence": evidence.to_dict()}

    def _pg_record_evidence(
        self,
        *,
        strategy: str,
        stage: str,
        service: str,
        report_type: str,
        artifact_path: Path | str,
        status: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        from db.evidence_repository import ReportRegistration
        from svos.adapters.artifacts import FilesystemArtifactStore

        entity, state = self._pg_current_state(strategy)

        artifact_store = FilesystemArtifactStore(self.root / "data" / "artifacts")
        stored = artifact_store.put(artifact_path)

        report_id = f"{strategy}:{stage}:{report_type}:{stored.sha256[:16]}"
        registration = ReportRegistration(
            report_id=report_id,
            strategy_id=entity.id,
            version_id=state.current_version_id,
            stage=stage,
            report_type=report_type,
            status=status,
            trust="QUALIFYING_REAL",
            schema_version="1.0",
            generator_version=f"svos-platform:{service}",
            json_artifact=stored,
        )
        report_uuid = self.pg_evidence_repo.register_report(registration)  # type: ignore[union-attr]

        binding_id = self.pg_evidence_repo.bind_evidence(  # type: ignore[union-attr]
            strategy_id=entity.id,
            version_id=state.current_version_id,
            stage=stage,
            artifact_sha256=stored.sha256,
            trust="QUALIFYING_REAL",
        )

        return {
            "report": {
                "report_id": report_id,
                "report_uuid": str(report_uuid),
                "status": status,
                "artifact_hash": stored.sha256,
            },
            "evidence": {
                "evidence_id": str(binding_id),
                "strategy": strategy,
                "stage": stage,
                "status": status,
                "metadata": {"report_id": report_id, **(metadata or {})},
            },
        }

    def audited_transition(
        self,
        strategy: str,
        *,
        to_stage: str,
        actor: str = "system",
        reason: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if self._pg_active:
            return self._pg_audited_transition(
                strategy,
                to_stage=to_stage,
                actor=actor,
                reason=reason,
                metadata=metadata,
            )
        transition = self.governance.transition(
            strategy,
            to_stage=to_stage,
            actor=actor,
            reason=reason,
            metadata=metadata,
        )
        return transition.to_dict()

    def _pg_audited_transition(
        self,
        strategy: str,
        *,
        to_stage: str,
        actor: str,
        reason: str,
        metadata: dict[str, Any] | None,
    ) -> dict[str, Any]:
        from db.control_plane import TransitionCommand

        entity, state = self._pg_current_state(strategy)
        evidence_ids = self._pg_collect_evidence_ids(
            strategy_id=entity.id,
            version_id=state.current_version_id,
            stage=state.current_stage,
        )
        command = TransitionCommand(
            strategy_slug=strategy,
            version_id=state.current_version_id,
            from_stage=state.current_stage,
            to_stage=to_stage,
            expected_revision=state.opt_lock,
            actor=actor,
            reason=reason,
            policy_version=_POLICY_VERSION,
            evidence_ids=evidence_ids,
        )
        result = self.pg_control_plane.commit_transition(command)  # type: ignore[union-attr]
        return {
            "from_stage": command.from_stage,
            "to_stage": to_stage,
            "actor": actor,
            "reason": reason,
            "metadata": {"governance_decision_id": str(result.decision_id), **(metadata or {})},
        }

    # ── helpers ────────────────────────────────────────────────────────────

    def _pg_current_state(self, strategy: str) -> tuple[Any, Any]:
        from sqlalchemy import select
        from db.models import StageState, StrategyEntity

        sf = self.pg_control_plane.session_factory  # type: ignore[union-attr]
        with sf() as session:
            entity = session.scalar(
                select(StrategyEntity).where(StrategyEntity.slug == strategy)
            )
            if entity is None:
                raise KeyError(f"strategy not seeded in PostgreSQL: {strategy}")
            state = session.scalar(
                select(StageState).where(StageState.strategy_id == entity.id)
            )
            if state is None:
                raise RuntimeError(f"no stage state in PostgreSQL for: {strategy}")
            # Detach from session so callers can read fields after session closes
            session.expunge_all()
            return entity, state

    def _pg_collect_evidence_ids(
        self,
        *,
        strategy_id: UUID,
        version_id: UUID | None,
        stage: str,
    ) -> tuple[UUID, ...]:
        if stage in _PG_NO_EVIDENCE_SOURCES:
            return ()
        from sqlalchemy import select
        from db.models import ArtifactBinding

        sf = self.pg_control_plane.session_factory  # type: ignore[union-attr]
        with sf() as session:
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

    # ── approval ───────────────────────────────────────────────────────────

    def approve_transition(
        self,
        strategy: str,
        *,
        to_stage: str,
        approver: str,
        reason: str,
    ) -> dict[str, Any]:
        return self.governance.record_approval(
            strategy,
            to_stage=to_stage,
            approver=approver,
            reason=reason,
        ).to_dict()

    # ── experiment tracking ────────────────────────────────────────────────

    def register_experiment(
        self,
        strategy: str,
        hypothesis: str,
        parameters: dict[str, Any],
        actor: str,
    ) -> ExperimentRecord:
        """Pre-register a research experiment before the pipeline run.

        Returns the ExperimentRecord with a deterministic experiment_id.
        Call complete_experiment() after the pipeline run with the outcome.
        """
        return self._experiments.register(strategy, hypothesis, parameters, actor=actor)

    def complete_experiment(
        self,
        experiment_id: str,
        *,
        run_id: str,
        status: str,
        verdict: str,
        metadata: dict[str, Any] | None = None,
    ) -> ExperimentRecord:
        """Mark a registered experiment as complete with its outcome.

        Args:
            experiment_id: ID returned by register_experiment().
            run_id: The run_id from the RunManifest for this pipeline run.
            status: Terminal status — PASS | FAIL | INCONCLUSIVE | RUNNING.
            verdict: Human-readable summary of why the experiment passed or failed.
            metadata: Optional key/value context (e.g. PF scores, trade counts).
        """
        return self._experiments.complete(
            experiment_id,
            run_id=run_id,
            status=status,
            verdict=verdict,
            metadata=metadata,
        )

    # ── summary ────────────────────────────────────────────────────────────

    def strategy_summary(self, strategy: str) -> dict[str, Any]:
        record = self.registry.ensure_strategy(strategy)
        return {
            "record": record.to_dict(),
            "versions": self.registry.versions(strategy),
            "transitions": self.registry.transitions(strategy),
            "evidence": self.registry.evidence(strategy),
            "gate_decisions": self.governance.decisions(strategy),
            "approvals": self.governance.approvals(strategy),
        }
