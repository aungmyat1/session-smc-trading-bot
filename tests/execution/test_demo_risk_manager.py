"""Tests for execution/demo_risk_manager.py"""

import pytest
from execution.demo_risk_manager import (
    calculate_lots,
    new_state,
    check_limits,
    record_result,
    reset_daily,
    LIMITS,
    _MIN_LOT,
    _MAX_LOT,
)


class TestCalculateLots:
    def test_basic_calculation(self):
        # $10k balance, 20 pip SL, 0.25% risk = $25 risk
        # $25 / (20 pips × $10/pip) = 0.125 lots → floor to 0.12
        lots = calculate_lots(10_000, 20, "EURUSD", 0.0025)
        assert lots == pytest.approx(0.12, abs=0.01)

    def test_respects_min_lot(self):
        lots = calculate_lots(100, 100, "EURUSD")
        assert lots >= _MIN_LOT

    def test_respects_max_lot(self):
        lots = calculate_lots(1_000_000, 1, "EURUSD")
        assert lots <= _MAX_LOT

    def test_zero_sl_returns_min(self):
        lots = calculate_lots(10_000, 0, "EURUSD")
        assert lots == _MIN_LOT

    def test_zero_balance_returns_min(self):
        lots = calculate_lots(0, 20, "EURUSD")
        assert lots == _MIN_LOT

    def test_result_is_multiple_of_0_01(self):
        lots = calculate_lots(5_000, 15, "EURUSD")
        assert round(lots / 0.01) == pytest.approx(lots / 0.01, abs=0.001)


class TestCheckLimits:
    def test_clean_state_approved(self):
        r = check_limits(new_state())
        assert r["approved"] is True

    def test_halted_rejected(self):
        s = new_state()
        s["halted"] = True
        s["halt_reason"] = "TEST"
        r = check_limits(s)
        assert r["approved"] is False
        assert "HALTED" in r["reason"] or "TEST" in r["reason"]

    def test_max_trades_per_day(self):
        s = new_state()
        s["trades_today"] = LIMITS["max_trades_per_day"]
        assert check_limits(s)["approved"] is False
        assert check_limits(s)["reason"] == "MAX_TRADES_PER_DAY"

    def test_max_open_positions(self):
        s = new_state()
        s["open_positions"] = LIMITS["max_open_positions"]
        assert check_limits(s)["approved"] is False

    def test_daily_loss_limit(self):
        s = new_state()
        s["daily_loss_pct"] = 0.016
        assert check_limits(s)["approved"] is False
        assert check_limits(s)["reason"] == "DAILY_LOSS_LIMIT"

    def test_consecutive_loss_limit(self):
        s = new_state()
        s["consecutive_losses"] = LIMITS["max_consecutive_losses"]
        assert check_limits(s)["approved"] is False


class TestRecordResult:
    def test_increments_trades_today(self):
        s = new_state()
        s = record_result(s, "WIN", 0.0025)
        assert s["trades_today"] == 1

    def test_resets_consecutive_on_win(self):
        s = new_state()
        s["consecutive_losses"] = 2
        s = record_result(s, "WIN", 0.0025)
        assert s["consecutive_losses"] == 0

    def test_increments_consecutive_on_loss(self):
        s = new_state()
        s = record_result(s, "LOSS", -0.0025)
        assert s["consecutive_losses"] == 1

    def test_accumulates_daily_loss(self):
        s = new_state()
        s = record_result(s, "LOSS", -0.005)
        assert s["daily_loss_pct"] == pytest.approx(0.005)

    def test_halts_on_daily_loss(self):
        s = new_state()
        s["daily_loss_pct"] = 0.013
        s = record_result(s, "LOSS", -0.005)
        assert s["halted"] is True

    def test_halts_on_consecutive_loss(self):
        s = new_state()
        s["consecutive_losses"] = 2
        s = record_result(s, "LOSS", -0.001)
        assert s["halted"] is True


class TestResetDaily:
    def test_clears_all_counters(self):
        s = new_state()
        s["trades_today"] = 3
        s["daily_loss_pct"] = 0.02
        s["halted"] = True
        s = reset_daily(s)
        assert s["trades_today"] == 0
        assert s["daily_loss_pct"] == 0.0
        assert s["halted"] is False

    def test_sets_last_reset(self):
        s = new_state()
        s = reset_daily(s)
        assert s["last_reset"] != ""
