"""Tests for bot/engine/risk_manager.py (Adaptive Engine — isolated from execution/)"""

import pytest
from adaptive.strategies import AdaptiveSignal
from adaptive.engine.risk_manager import (
    new_state,
    check_risk,
    record_trade,
    reset_daily,
)


def _signal(pair: str = "EURUSD", direction: str = "LONG") -> AdaptiveSignal:
    return AdaptiveSignal(
        strategy="smc_session",
        pair=pair,
        direction=direction,
        entry_price=1.1000,
        sl_price=1.0950,
        tp_price=1.1150,
        session="london",
        timestamp="2026-06-24T07:30:00+00:00",
        reason="test",
    )


class TestNewState:
    def test_initial_state_not_halted(self):
        state = new_state()
        assert state["halted"] is False

    def test_initial_trades_zero(self):
        state = new_state()
        assert state["trades_today"] == 0

    def test_initial_loss_zero(self):
        state = new_state()
        assert state["daily_loss_pct"] == 0.0


class TestCheckRisk:
    def test_approves_clean_state(self):
        state = new_state()
        result = check_risk(_signal(), state)
        assert result["approved"] is True
        assert result["rejection_reason"] == ""

    def test_rejects_when_halted(self):
        state = new_state()
        state["halted"] = True
        result = check_risk(_signal(), state)
        assert result["approved"] is False
        assert "not_halted" in result["checks"]
        assert result["checks"]["not_halted"] is False

    def test_rejects_when_daily_loss_exceeded(self):
        state = new_state()
        state["daily_loss_pct"] = 0.02  # > 1.5% limit
        result = check_risk(_signal(), state)
        assert result["approved"] is False
        assert result["checks"]["daily_loss_ok"] is False

    def test_rejects_when_trade_count_exceeded(self):
        state = new_state()
        state["trades_today"] = 6
        result = check_risk(_signal(), state)
        assert result["approved"] is False
        assert result["checks"]["trade_count_ok"] is False

    def test_rejects_when_consecutive_losses_exceeded(self):
        state = new_state()
        state["consecutive_losses"] = 3
        result = check_risk(_signal(), state)
        assert result["approved"] is False
        assert result["checks"]["consec_loss_ok"] is False

    def test_rejects_correlated_long_long(self):
        state = new_state()
        state["open_positions"] = [{"pair": "EURUSD", "direction": "LONG"}]
        result = check_risk(_signal("GBPUSD", "LONG"), state)
        assert result["approved"] is False
        assert result["checks"]["no_correlation"] is False

    def test_allows_long_short_different_pair(self):
        state = new_state()
        state["open_positions"] = [{"pair": "EURUSD", "direction": "LONG"}]
        result = check_risk(_signal("GBPUSD", "SHORT"), state)
        assert result["checks"]["no_correlation"] is True

    def test_allows_same_direction_uncorrelated_pair(self):
        state = new_state()
        state["open_positions"] = [{"pair": "EURUSD", "direction": "LONG"}]
        result = check_risk(_signal("USDJPY", "LONG"), state)
        assert result["checks"]["no_correlation"] is True

    def test_rejection_reason_names_failures(self):
        state = new_state()
        state["halted"] = True
        result = check_risk(_signal(), state)
        assert "not_halted" in result["rejection_reason"]


class TestRecordTrade:
    def test_increments_trade_count(self):
        state = new_state()
        state = record_trade(
            {"pair": "EURUSD", "direction": "LONG", "pnl_pct": 0.005, "outcome": "WIN"},
            state,
        )
        assert state["trades_today"] == 1

    def test_resets_consecutive_on_win(self):
        state = new_state()
        state["consecutive_losses"] = 2
        state = record_trade(
            {"pair": "EURUSD", "direction": "LONG", "pnl_pct": 0.005, "outcome": "WIN"},
            state,
        )
        assert state["consecutive_losses"] == 0

    def test_increments_consecutive_on_loss(self):
        state = new_state()
        state = record_trade(
            {
                "pair": "EURUSD",
                "direction": "LONG",
                "pnl_pct": -0.005,
                "outcome": "LOSS",
            },
            state,
        )
        assert state["consecutive_losses"] == 1

    def test_accumulates_daily_loss(self):
        state = new_state()
        state = record_trade(
            {
                "pair": "EURUSD",
                "direction": "LONG",
                "pnl_pct": -0.005,
                "outcome": "LOSS",
            },
            state,
        )
        assert state["daily_loss_pct"] == pytest.approx(0.005)

    def test_halts_on_daily_loss_limit(self):
        state = new_state()
        state["daily_loss_pct"] = 0.014
        state = record_trade(
            {
                "pair": "EURUSD",
                "direction": "LONG",
                "pnl_pct": -0.003,
                "outcome": "LOSS",
            },
            state,
        )
        assert state["halted"] is True
        assert state["halt_reason"] == "DAILY_LOSS_LIMIT_HIT"

    def test_halts_on_consecutive_loss_limit(self):
        state = new_state()
        state["consecutive_losses"] = 2
        state = record_trade(
            {
                "pair": "EURUSD",
                "direction": "LONG",
                "pnl_pct": -0.003,
                "outcome": "LOSS",
            },
            state,
        )
        assert state["halted"] is True
        assert state["halt_reason"] == "CONSECUTIVE_LOSS_LIMIT_HIT"

    def test_removes_closed_position(self):
        state = new_state()
        state["open_positions"] = [{"pair": "EURUSD", "direction": "LONG"}]
        state = record_trade(
            {"pair": "EURUSD", "direction": "LONG", "pnl_pct": 0.005, "outcome": "WIN"},
            state,
        )
        assert state["open_positions"] == []


class TestResetDaily:
    def test_clears_daily_counters(self):
        state = new_state()
        state["daily_loss_pct"] = 0.05
        state["trades_today"] = 5
        state["halted"] = True
        state = reset_daily(state)
        assert state["daily_loss_pct"] == 0.0
        assert state["trades_today"] == 0
        assert state["halted"] is False
