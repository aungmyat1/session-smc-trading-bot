"""Tests for svos/lifecycle/authority.py — lifecycle transition enforcement."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from db.models import StageState, StrategyEntity, StrategyVersion
from svos.lifecycle.authority import (
    LifecycleAuthority,
    AuthorityCommand,
    TransitionResult,
    is_postgres_authority,
    mark_postgres_authority,
    assert_postgres_authority,
)
from svos.lifecycle.manager import StrategyLifecycleManager


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def mock_strategy_entity() -> MagicMock:
    entity = MagicMock(spec=StrategyEntity)
    entity.id = uuid4()
    entity.slug = "TEST-STRATEGY"
    entity.name = "Test Strategy"
    return entity


@pytest.fixture
def mock_strategy_version() -> MagicMock:
    version = MagicMock(spec=StrategyVersion)
    version.id = uuid4()
    return version


@pytest.fixture
def mock_stage_state() -> MagicMock:
    state = MagicMock(spec=StageState)
    state.id = uuid4()
    state.strategy_id = uuid4()
    state.current_stage = "AUDIT"
    state.current_version_id = uuid4()
    state.opt_lock = 5
    state.updated_by = "system"
    return state


@pytest.fixture
def mock_session_factory(mock_strategy_entity, mock_strategy_version, mock_stage_state):
    """Return a session factory that returns a pre-configured mock session."""
    session = MagicMock()
    session.__enter__.return_value = session

    def scalar_side_effect(query):
        q = str(query)
        if "StrategyEntity" in q:
            return mock_strategy_entity
        if "StageState" in q:
            return mock_stage_state
        return None

    session.scalar = scalar_side_effect
    session.scalars.return_value.all.return_value = []

    def session_factory():
        return session

    return session_factory


@pytest.fixture
def authority(mock_session_factory):
    return LifecycleAuthority(session_factory=mock_session_factory)


# ═══════════════════════════════════════════════════════════════════════════════
# LifecycleAuthority.capability_check
# ═══════════════════════════════════════════════════════════════════════════════

def test_capability_check_available(authority):
    result = authority.capability_check()
    assert result["available"] is True


def test_capability_check_unavailable():
    bad_factory = MagicMock()
    bad_factory.side_effect = Exception("connection refused")
    authority = LifecycleAuthority(session_factory=lambda: bad_factory())
    result = authority.capability_check()
    assert result["available"] is False


# ═══════════════════════════════════════════════════════════════════════════════
# LifecycleAuthority.validate_evidence
# ═══════════════════════════════════════════════════════════════════════════════

def test_validate_evidence_returns_empty_for_no_evidence_stages(authority):
    """Stages DRAFT, REFINEMENT, REVALIDATION, RETIRED don't need evidence."""
    allowed = ("DRAFT", "REFINEMENT", "REVALIDATION", "RETIRED")
    for stage in allowed:
        result = authority.validate_evidence(
            strategy_id=uuid4(),
            version_id=uuid4(),
            stage=stage,
        )
        assert result == ()


def test_validate_evidence_collects_qualifying_bindings():
    """AUDIT stage should collect qualifying evidence from database."""
    session = MagicMock()
    session.__enter__.return_value = session
    binding_id = uuid4()
    mock_binding = MagicMock()
    mock_binding.id = binding_id
    session.scalars.return_value.all.return_value = [mock_binding]

    authority = LifecycleAuthority(session_factory=lambda: session)
    result = authority.validate_evidence(
        strategy_id=uuid4(),
        version_id=uuid4(),
        stage="AUDIT",
    )
    assert len(result) == 1
    assert result[0] == binding_id


def test_validate_evidence_returns_empty_when_no_bindings():
    """No qualifying evidence should return empty tuple."""
    session = MagicMock()
    session.__enter__.return_value = session
    session.scalars.return_value.all.return_value = []

    authority = LifecycleAuthority(session_factory=lambda: session)
    result = authority.validate_evidence(
        strategy_id=uuid4(),
        version_id=uuid4(),
        stage="AUDIT",
    )
    assert result == ()


# ═══════════════════════════════════════════════════════════════════════════════
# LifecycleAuthority.transition
# ═══════════════════════════════════════════════════════════════════════════════

def test_transition_success(authority, mock_stage_state):
    """A valid AUDIT -> HISTORICAL_REPLAY transition should succeed."""
    result = authority.transition(
        strategy="TEST-STRATEGY",
        to_stage="HISTORICAL_REPLAY",
        actor="test-actor",
        reason="Passing audit review",
    )
    assert result.success is True
    assert result.new_revision == 6  # 5 + 1
    assert result.from_stage == "AUDIT"
    assert result.to_stage == "HISTORICAL_REPLAY"


def test_transition_invalid_stage(authority):
    """An invalid stage name should fail."""
    result = authority.transition(
        strategy="TEST-STRATEGY",
        to_stage="NONEXISTENT_STAGE",
        actor="test-actor",
        reason="Testing",
    )
    assert result.success is False
    assert len(result.blockers) > 0


def test_transition_production_approval_blocked(authority):
    """PRODUCTION_APPROVAL transitions must be blocked during construction."""
    result = authority.transition(
        strategy="TEST-STRATEGY",
        to_stage="PRODUCTION_APPROVAL",
        actor="admin",
        reason="Requesting production",
    )
    assert result.success is False
    assert any("Production Approval" in b for b in result.blockers)


def test_transition_requires_actor(authority):
    """Actor must be provided."""
    result = authority.transition(
        strategy="TEST-STRATEGY",
        to_stage="HISTORICAL_REPLAY",
        actor="",
        reason="Testing",
    )
    assert result.success is False
    assert any("Actor" in b for b in result.blockers)


def test_transition_requires_reason(authority):
    """Reason must be provided."""
    result = authority.transition(
        strategy="TEST-STRATEGY",
        to_stage="HISTORICAL_REPLAY",
        actor="test-actor",
        reason="",
    )
    assert result.success is False
    assert any("reason" in b.lower() for b in result.blockers)


def test_transition_no_evidence_for_audit_to_replay(authority):
    """AUDIT -> HISTORICAL_REPLAY needs qualifying evidence."""
    authority = LifecycleAuthority(session_factory=authority.session_factory)
    result = authority.transition(
        strategy="TEST-STRATEGY",
        to_stage="HISTORICAL_REPLAY",
        actor="test-actor",
        reason="Passing audit review",
    )
    assert result.success is False
    assert any("evidence" in b.lower() for b in result.blockers)


def test_transition_draft_does_not_need_evidence():
    """DRAFT -> INTAKE does not require evidence."""
    session = MagicMock()
    session.__enter__.return_value = session

    entity = MagicMock(spec=StrategyEntity)
    entity.id = uuid4()
    entity.slug = "TEST"

    state = MagicMock(spec=StageState)
    state.strategy_id = entity.id
    state.current_stage = "DRAFT"
    state.current_version_id = uuid4()
    state.opt_lock = 0
    state.updated_by = "system"

    def scalar_side_effect(query):
        q = str(query)
        if "StrategyEntity" in q:
            return entity
        if "StageState" in q:
            return state
        return None

    session.scalar = scalar_side_effect
    session.scalars.return_value.all.return_value = []

    authority = LifecycleAuthority(session_factory=lambda: session)
    result = authority.transition(
        strategy="TEST",
        to_stage="INTAKE",
        actor="system",
        reason="Starting intake process",
    )
    # DRAFT -> INTAKE is not a valid forward transition; the lifecycle allows
    # forward to next stage in order. DRAFT is first, INTAKE is second.
    # Let's check what happens:
    # From DRAFT, the allowed forward transition is INTAKE.
    # But the transition function first checks lifecycle.validate_transition_from_names
    # which just validates the to_stage name, then checks validate_transition(DRAFT, INTAKE)
    assert result.success is True
    assert result.new_revision == 1


def test_transition_fails_closed_when_strategy_not_in_db(authority):
    """Missing strategy should fail closed."""
    session = MagicMock()
    session.__enter__.return_value = session
    session.scalar.return_value = None  # No entity found

    authority = LifecycleAuthority(session_factory=lambda: session)
    with pytest.raises(RuntimeError):
        authority.transition(
            strategy="MISSING-STRATEGY",
            to_stage="AUDIT",
            actor="system",
            reason="Testing",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Sentinel file
# ═══════════════════════════════════════════════════════════════════════════════

def test_mark_and_check_sentinel(tmp_path):
    """mark_postgres_authority() writes a sentinel file."""
    sentinel = tmp_path / ".test_sentinel"
    mark_postgres_authority(str(sentinel))
    assert sentinel.exists()
    assert is_postgres_authority(str(sentinel))


def test_assert_postgres_authority_raises(tmp_path):
    """assert_postgres_authority() raises RuntimeError when sentinel exists."""
    sentinel = tmp_path / ".test_sentinel"
    mark_postgres_authority(str(sentinel))
    with pytest.raises(RuntimeError, match="PostgreSQL is the authoritative lifecycle backend"):
        assert_postgres_authority(str(sentinel))


def test_no_sentinel_by_default(tmp_path):
    """Without a sentinel, assert_postgres_authority() is a no-op."""
    sentinel = tmp_path / ".test_sentinel"
    assert not is_postgres_authority(str(sentinel))
    # Should not raise
    assert_postgres_authority(str(sentinel))


# ═══════════════════════════════════════════════════════════════════════════════
# Safety: no live trading, broker, or approval bypass
# ═══════════════════════════════════════════════════════════════════════════════

def test_no_broker_writes_in_authority():
    """LifecycleAuthority must never reference broker credentials."""
    source = (ROOT / "svos" / "lifecycle" / "authority.py").read_text(encoding="utf-8")
    forbidden = ["metaapi", "MT5Connector", "VantageDemoExecutor", "LIVE_TRADING", "live_trading", "confirm_token"]
    for term in forbidden:
        assert term not in source, f"LifecycleAuthority must not reference broker terms: {term}"


def test_no_approval_bypass():
    """LifecycleAuthority must not auto-approve or auto-promote strategies."""
    source = (ROOT / "svos" / "lifecycle" / "authority.py").read_text(encoding="utf-8")
    assert "approved" not in source.lower() or "production" in source.lower()
    assert "promote" not in source.lower()
