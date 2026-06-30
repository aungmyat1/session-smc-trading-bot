"""Tests for execution/risk_manager.py"""

from datetime import datetime, timezone

import pytest

from execution.risk_manager import RiskManager

BASE_CONFIG = {
    "risk": {
        "risk_per_trade_pct": 0.5,
        "max_open_trades": 2,
        "max_pair_exposure": 1,
        "max_daily_loss_r": 3.0,
        "max_weekly_loss_r": 8.0,
        "max_consecutive_losses": 5,
        "min_lot": 0.01,
        "max_lot": 10.0,
    },
    "pip_value_per_lot": {"EURUSD": 10.0, "GBPUSD": 10.0},
}


@pytest.fixture(autouse=True)
def isolate_state_file(tmp_path, monkeypatch):
    """Redirect STATE_FILE to a temp dir so tests don't touch logs/."""
    fake = tmp_path / "bot_state.json"
    monkeypatch.setattr("execution.risk_manager.STATE_FILE", fake)
    yield


def make_rm() -> RiskManager:
    return RiskManager(BASE_CONFIG)


# ── Lot sizing ────────────────────────────────────────────────────────────────


class TestLotSizing:
    def test_basic(self):
        rm = make_rm()
        # balance=10000, risk=0.5% → risk_amount=50
        # sl=50pips, pip_value=10 → lot=50/500=0.10
        lot = rm.calculate_lot_size(10_000, 50.0, "EURUSD")
        assert lot == pytest.approx(0.10)

    def test_minimum_lot_enforced(self):
        rm = make_rm()
        # Very wide SL → lot would be tiny
        lot = rm.calculate_lot_size(100, 500.0, "EURUSD")
        assert lot == 0.01

    def test_maximum_lot_enforced(self):
        rm = make_rm()
        # Huge balance, tight SL → lot would exceed max
        lot = rm.calculate_lot_size(100_000_000, 1.0, "EURUSD")
        assert lot == 10.0

    def test_invalid_sl_raises(self):
        rm = make_rm()
        with pytest.raises(ValueError):
            rm.calculate_lot_size(10_000, 0, "EURUSD")

    def test_rounding(self):
        rm = make_rm()
        lot = rm.calculate_lot_size(12_345, 37.0, "EURUSD")
        # Ensure result has at most 2 decimal places
        assert lot == round(lot, 2)


# ── Position guards ───────────────────────────────────────────────────────────


class FakePosition:
    def __init__(self, symbol):
        self.symbol = symbol


class TestPositionGuards:
    def test_can_open_when_empty(self):
        rm = make_rm()
        ok, reason = rm.can_open_position("EURUSD", [])
        assert ok
        assert reason == ""

    def test_blocked_at_max_open_trades(self):
        rm = make_rm()
        positions = [FakePosition("EURUSD"), FakePosition("GBPUSD")]
        ok, reason = rm.can_open_position("EURUSD", positions)
        assert not ok
        assert "MAX_OPEN_TRADES" in reason

    def test_blocked_at_max_pair_exposure(self):
        rm = make_rm()
        positions = [FakePosition("EURUSD")]
        ok, reason = rm.can_open_position("EURUSD", positions)
        assert not ok
        assert "MAX_PAIR_EXPOSURE" in reason

    def test_can_open_different_pair(self):
        rm = make_rm()
        positions = [FakePosition("EURUSD")]
        ok, _ = rm.can_open_position("GBPUSD", positions)
        assert ok


# ── Circuit breakers ──────────────────────────────────────────────────────────


class TestCircuitBreakers:
    def test_clean_start(self):
        rm = make_rm()
        cb = rm.check_circuit_breakers()
        assert not cb.halted

    def test_daily_loss_triggers_halt(self):
        rm = make_rm()
        rm.record_trade_result(-1.0)
        rm.record_trade_result(-1.0)
        rm.record_trade_result(-1.0)
        cb = rm.check_circuit_breakers()
        assert cb.halted
        assert cb.reason == "MAX_DAILY_LOSS"

    def test_consecutive_losses_triggers_halt(self):
        rm = make_rm()
        for _ in range(5):
            rm.record_trade_result(-0.1)
        cb = rm.check_circuit_breakers()
        assert cb.halted
        assert cb.reason == "MAX_CONSECUTIVE_LOSSES"

    def test_win_resets_consecutive_counter(self):
        rm = make_rm()
        rm.record_trade_result(-0.5)
        rm.record_trade_result(-0.5)
        rm.record_trade_result(2.0)  # win resets streak
        assert rm.state.consecutive_losses == 0
        cb = rm.check_circuit_breakers()
        assert not cb.halted

    def test_daily_reset_clears_daily_halt(self):
        rm = make_rm()
        for _ in range(3):
            rm.record_trade_result(-1.1)

        assert rm.state.halted

        # Simulate next day
        tomorrow = datetime(2030, 1, 2, tzinfo=timezone.utc)
        rm._maybe_reset(tomorrow)
        assert not rm.state.halted
        assert rm.state.daily_loss_r == 0.0

    def test_state_persists_across_instances(self, tmp_path, monkeypatch):
        fake = tmp_path / "bot_state.json"
        monkeypatch.setattr("execution.risk_manager.STATE_FILE", fake)

        rm1 = RiskManager(BASE_CONFIG)
        rm1.record_trade_result(-1.0)
        rm1.record_trade_result(-1.0)
        consecutive = rm1.state.consecutive_losses

        rm2 = RiskManager(BASE_CONFIG)
        assert rm2.state.consecutive_losses == consecutive
