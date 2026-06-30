from __future__ import annotations

import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.control_plane import (
    ControlPlaneConflict,
    PostgresControlPlane,
    TransitionCommand,
)
from db.evidence_repository import PostgresEvidenceRepository
from db.models import (
    ArtifactBinding,
    ReportRecord,
    StageState,
    StrategyEntity,
    StrategyVersion,
)
from svos.orchestration.service import SVOSPlatform

TEST_DATABASE_URL = os.getenv("SVOS_TEST_DATABASE_URL", "")
pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL, reason="SVOS_TEST_DATABASE_URL is not configured"
)


def _fresh_sessions():
    engine = create_engine(TEST_DATABASE_URL)
    return sessionmaker(bind=engine, expire_on_commit=False)


def _catalog_yaml(name: str, status: str = "draft", version: str = "0.1") -> str:
    return f"""
current_strategy: null
strategies:
  {name}:
    status: {status}
    approved: false
    current: false
    version: '{version}'
    owner: integration-test
    description: Integration test strategy
""".lstrip()


def _setup_catalog(tmp_path: Path, name: str, status: str = "draft") -> Path:
    cfg = tmp_path / "config"
    cfg.mkdir(parents=True, exist_ok=True)
    (cfg / "strategy_catalog.yaml").write_text(_catalog_yaml(name, status=status))
    return cfg / "strategy_catalog.yaml"


def test_migrations_and_concurrent_transition_are_atomic() -> None:
    env = {**os.environ, "DATABASE_URL": TEST_DATABASE_URL}
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    engine = create_engine(TEST_DATABASE_URL)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    slug = f"concurrency-{uuid4()}"
    with sessions.begin() as session:
        strategy = StrategyEntity(name=slug, slug=slug, owner="integration-test")
        session.add(strategy)
        session.flush()
        version = StrategyVersion(
            strategy_id=strategy.id,
            version="1.0.0",
            spec_hash="a" * 64,
            rules_json={"test": True},
            created_by="integration-test",
        )
        session.add(version)
        session.flush()
        session.add(
            StageState(
                strategy_id=strategy.id,
                current_stage="DRAFT",
                current_version_id=version.id,
                opt_lock=0,
                updated_by="integration-test",
            )
        )
        version_id = version.id

    repository = PostgresControlPlane(sessions)
    command = TransitionCommand(
        strategy_slug=slug,
        version_id=version_id,
        from_stage="DRAFT",
        to_stage="INTAKE",
        expected_revision=0,
        actor="integration-test",
        reason="prove optimistic concurrency",
        policy_version="test-v1",
    )

    def attempt() -> str:
        try:
            repository.commit_transition(command)
            return "committed"
        except ControlPlaneConflict:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(lambda _: attempt(), range(2)))
    assert sorted(outcomes) == ["committed", "conflict"]

    with sessions() as session:
        strategy = session.query(StrategyEntity).filter_by(slug=slug).one()
        state = session.query(StageState).filter_by(strategy_id=strategy.id).one()
        assert state.current_stage == "INTAKE"
        assert state.opt_lock == 1


# ── P1-1 tests: SVOSPlatform with PostgreSQL backends ────────────────────────


def test_svos_platform_bootstrap_seeds_postgres(tmp_path: Path) -> None:
    name = f"p11-boot-{uuid4().hex[:8]}"
    catalog = _setup_catalog(tmp_path, name, status="draft")
    sessions = _fresh_sessions()
    pg = PostgresControlPlane(sessions)
    ev = PostgresEvidenceRepository(sessions)

    platform = SVOSPlatform(
        root=tmp_path, catalog_path=catalog, pg_control_plane=pg, pg_evidence_repo=ev
    )
    result = platform.bootstrap()

    assert result["strategy_count"] == 1

    # JSONL store must NOT have been written
    jsonl_dir = tmp_path / "data" / "svos" / "registry"
    assert not jsonl_dir.exists(), "bootstrap() wrote JSONL when PG is active"

    # PG rows must exist
    with sessions() as session:
        entity = session.query(StrategyEntity).filter_by(slug=name).one()
        state = session.query(StageState).filter_by(strategy_id=entity.id).one()
        assert state.current_stage == "DRAFT"
        assert state.opt_lock == 0


def test_svos_platform_transition_routes_to_postgres(tmp_path: Path) -> None:
    name = f"p11-trans-{uuid4().hex[:8]}"
    catalog = _setup_catalog(tmp_path, name, status="draft")
    sessions = _fresh_sessions()
    pg = PostgresControlPlane(sessions)
    ev = PostgresEvidenceRepository(sessions)

    platform = SVOSPlatform(
        root=tmp_path, catalog_path=catalog, pg_control_plane=pg, pg_evidence_repo=ev
    )
    platform.bootstrap()

    # DRAFT → INTAKE requires no evidence
    result = platform.audited_transition(
        name, to_stage="INTAKE", actor="integration-test", reason="P1-1 smoke test"
    )

    assert result["from_stage"] == "DRAFT"
    assert result["to_stage"] == "INTAKE"
    assert result["metadata"]["governance_decision_id"]

    # JSONL governance directory must NOT have been written
    jsonl_gov = tmp_path / "data" / "svos" / "governance"
    assert not jsonl_gov.exists(), "audited_transition() wrote JSONL when PG is active"

    # PG state updated
    with sessions() as session:
        entity = session.query(StrategyEntity).filter_by(slug=name).one()
        state = session.query(StageState).filter_by(strategy_id=entity.id).one()
        assert state.current_stage == "INTAKE"
        assert state.opt_lock == 1


def test_svos_platform_evidence_routes_to_postgres(tmp_path: Path) -> None:
    name = f"p11-evid-{uuid4().hex[:8]}"
    catalog = _setup_catalog(tmp_path, name, status="draft")
    sessions = _fresh_sessions()
    pg = PostgresControlPlane(sessions)
    ev = PostgresEvidenceRepository(sessions)

    platform = SVOSPlatform(
        root=tmp_path, catalog_path=catalog, pg_control_plane=pg, pg_evidence_repo=ev
    )
    platform.bootstrap()

    artifact = tmp_path / "audit.json"
    artifact.write_text(json.dumps({"status": "PASS"}))

    recorded = platform.record_report_evidence(
        strategy=name,
        stage="DRAFT",
        service="svos",
        report_type="audit.json",
        artifact_path=artifact,
        status="PASS",
        metadata={"source": "integration-test"},
    )

    # No JSONL evidence file
    jsonl_ev = tmp_path / "data" / "svos" / "registry" / name / "evidence.jsonl"
    assert (
        not jsonl_ev.exists()
    ), "record_report_evidence() wrote JSONL when PG is active"

    # PG ReportRecord exists
    with sessions() as session:
        report = (
            session.query(ReportRecord)
            .filter_by(report_id=recorded["report"]["report_id"])
            .first()
        )
        assert report is not None
        assert report.status == "PASS"

    # ArtifactBinding created (for future transition evidence validation)
    with sessions() as session:
        entity = session.query(StrategyEntity).filter_by(slug=name).one()
        binding = (
            session.query(ArtifactBinding)
            .filter_by(strategy_id=entity.id, stage="DRAFT")
            .first()
        )
        assert binding is not None
        assert binding.trust == "QUALIFYING_REAL"
        assert str(binding.id) == recorded["evidence"]["evidence_id"]
