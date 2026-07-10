"""Tests for execution/validation_session.py — Demo Validation Mode session tracking.

Uses a mocked DB session (same approach as test_risk_portfolio_store.py) so
CI does not require a live Postgres connection.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

_MODULE = "execution.validation_session"


@pytest.fixture()
def _mock_session():
    session = MagicMock()
    session_factory = MagicMock(return_value=session)
    with patch(f"{_MODULE}.SessionLocal", session_factory):
        yield session


@pytest.fixture()
def manager(_mock_session):
    from execution.validation_session import ValidationSessionManager
    return ValidationSessionManager()


class TestStart:
    def test_returns_a_session_id_and_persists_a_row(self, manager, _mock_session):
        session_id = manager.start(operator="alice", broker="vantage-mt5-demo", account="12345")
        assert session_id.startswith("val-")
        assert _mock_session.add.called
        assert _mock_session.commit.called

    def test_db_failure_is_swallowed_and_still_returns_an_id(self, manager, _mock_session):
        _mock_session.commit.side_effect = RuntimeError("db down")
        session_id = manager.start(operator="alice", broker="vantage-mt5-demo", account="12345")
        assert session_id.startswith("val-")
        assert _mock_session.rollback.called

    def test_no_database_configured_still_returns_an_id(self):
        with patch(f"{_MODULE}.SessionLocal", None):
            from execution.validation_session import ValidationSessionManager
            session_id = ValidationSessionManager().start(operator="a", broker="b", account="c")
            assert session_id.startswith("val-")


class TestResumeAndActiveSession:
    def test_resume_returns_none_when_not_found(self, manager, _mock_session):
        _mock_session.query.return_value.filter_by.return_value.first.return_value = None
        assert manager.resume("val-missing") is None

    def test_active_session_returns_none_when_database_unconfigured(self):
        with patch(f"{_MODULE}.SessionLocal", None):
            from execution.validation_session import ValidationSessionManager
            assert ValidationSessionManager().active_session() is None


class TestEnd:
    def test_end_updates_status_and_ended_at(self, manager, _mock_session):
        row = MagicMock(status="active", ended_at=None)
        _mock_session.query.return_value.filter_by.return_value.first.return_value = row
        manager.end("val-abc", status="completed")
        assert row.status == "completed"
        assert row.ended_at is not None
        assert _mock_session.commit.called


class TestConfigHash:
    def test_config_hash_is_deterministic_for_same_bytes(self, tmp_path):
        from execution.validation_session import config_hash
        config_file = tmp_path / "demo_validation.yaml"
        config_file.write_text("execution:\n  mode: demo_validation\n", encoding="utf-8")
        assert config_hash(config_file) == config_hash(config_file)

    def test_config_hash_returns_unknown_for_missing_file(self, tmp_path):
        from execution.validation_session import config_hash
        assert config_hash(tmp_path / "missing.yaml") == "unknown"
