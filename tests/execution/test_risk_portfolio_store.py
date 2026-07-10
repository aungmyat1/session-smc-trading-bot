"""Tests for execution/risk_portfolio_store.py — durable risk/portfolio state.

Uses a mocked DB session (same approach as test_operations_recorder.py) so CI
does not require a live Postgres connection.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

# Import after patching SessionLocal to avoid real DB connection attempt.
_STORE_MODULE = "execution.risk_portfolio_store"


@pytest.fixture()
def _mock_session():
    """Patch ``db.connection.SessionLocal`` to return a mock session."""
    session = MagicMock()
    session_factory = MagicMock(return_value=session)
    with patch(f"{_STORE_MODULE}.SessionLocal", session_factory):
        yield session


@pytest.fixture()
def store(_mock_session):
    from execution.risk_portfolio_store import RiskPortfolioStore
    return RiskPortfolioStore()


# ── Save / load round-trip (mocked) ──────────────────────────────────────


class TestSaveRiskState:
    def test_inserts_new_row_when_none_exists(self, store, _mock_session):
        _mock_session.query.return_value.filter_by.return_value.first.return_value = None

        store.save_risk_state(
            {"halted": False, "consecutive_losses": 0},
            runtime_id="test-run-1",
        )

        _mock_session.add.assert_called_once()
        _mock_session.commit.assert_called_once()

    def test_updates_existing_row(self, store, _mock_session):
        existing = MagicMock()
        existing.state_data = {"halted": False}
        _mock_session.query.return_value.filter_by.return_value.first.return_value = existing

        new_data = {"halted": True, "halt_reason": "CONSECUTIVE_LOSS_LIMIT"}
        store.save_risk_state(new_data, runtime_id="test-run-1")

        assert existing.state_data == new_data
        _mock_session.commit.assert_called_once()
        # No add() call for the state row when updating (only session.commit)
        # History is not appended for tick_save events.
        _mock_session.add.assert_not_called()

    def test_history_row_appended_for_trade_close(self, store, _mock_session):
        _mock_session.query.return_value.filter_by.return_value.first.return_value = None

        store.save_risk_state(
            {"consecutive_losses": 1},
            runtime_id="test-run-1",
            event="trade_close",
        )

        # Two add() calls: one for the state row, one for the history row.
        assert _mock_session.add.call_count == 2

    def test_no_history_row_for_tick_save(self, store, _mock_session):
        _mock_session.query.return_value.filter_by.return_value.first.return_value = None

        store.save_risk_state(
            {"consecutive_losses": 0},
            runtime_id="test-run-1",
            event="tick_save",
        )

        # Only one add() call: the state row.
        assert _mock_session.add.call_count == 1

    def test_history_row_appended_for_daily_reset(self, store, _mock_session):
        _mock_session.query.return_value.filter_by.return_value.first.return_value = None

        store.save_risk_state(
            {"trades_today": 0},
            runtime_id="test-run-1",
            event="daily_reset",
        )

        assert _mock_session.add.call_count == 2


class TestSavePortfolioState:
    def test_inserts_new_row(self, store, _mock_session):
        _mock_session.query.return_value.filter_by.return_value.first.return_value = None

        store.save_portfolio_state(
            {"daily_pnl_pct": 0.0, "open_symbols": []},
            runtime_id="test-run-1",
        )

        _mock_session.add.assert_called_once()
        _mock_session.commit.assert_called_once()


class TestLoadRiskState:
    def test_returns_state_data_when_row_exists(self, store, _mock_session):
        row = MagicMock()
        row.state_data = {"halted": False, "consecutive_losses": 2}
        _mock_session.query.return_value.filter_by.return_value.order_by.return_value.first.return_value = row

        result = store.load_risk_state()

        assert result == {"halted": False, "consecutive_losses": 2}

    def test_returns_none_when_no_row(self, store, _mock_session):
        _mock_session.query.return_value.filter_by.return_value.order_by.return_value.first.return_value = None

        result = store.load_risk_state()

        assert result is None


class TestLoadPortfolioState:
    def test_returns_state_data_when_row_exists(self, store, _mock_session):
        row = MagicMock()
        row.state_data = {"weekly_pnl_pct": -0.01, "open_symbols": ["EURUSD"]}
        _mock_session.query.return_value.filter_by.return_value.order_by.return_value.first.return_value = row

        result = store.load_portfolio_state()

        assert result == {"weekly_pnl_pct": -0.01, "open_symbols": ["EURUSD"]}


# ── Graceful degradation ─────────────────────────────────────────────────


class TestGracefulDegradation:
    def test_save_swallows_db_error(self, store, _mock_session):
        _mock_session.query.side_effect = RuntimeError("DB connection lost")

        # Must not raise.
        store.save_risk_state({"halted": False}, runtime_id="test-run-1")

        _mock_session.rollback.assert_called_once()

    def test_load_returns_none_on_db_error(self, store, _mock_session):
        _mock_session.query.side_effect = RuntimeError("DB connection lost")

        result = store.load_risk_state()

        assert result is None

    def test_save_noop_when_session_local_is_none(self):
        with patch(f"{_STORE_MODULE}.SessionLocal", None):
            from execution.risk_portfolio_store import RiskPortfolioStore
            s = RiskPortfolioStore()
            # Must not raise.
            s.save_risk_state({"halted": False}, runtime_id="r1")

    def test_load_returns_none_when_session_local_is_none(self):
        with patch(f"{_STORE_MODULE}.SessionLocal", None):
            from execution.risk_portfolio_store import RiskPortfolioStore
            s = RiskPortfolioStore()
            assert s.load_risk_state() is None
