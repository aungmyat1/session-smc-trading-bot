from __future__ import annotations

import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.control_plane import ControlPlaneConflict, PostgresControlPlane, TransitionCommand
from db.models import StageState, StrategyEntity, StrategyVersion


TEST_DATABASE_URL = os.getenv("SVOS_TEST_DATABASE_URL", "")
pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="SVOS_TEST_DATABASE_URL is not configured")


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
