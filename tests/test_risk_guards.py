"""
Smoke tests for risk guards and qualification engine.

Tests:
- DailyLossGuard halt/reset
- DrawdownGuard kill switch
- ConsecutiveLossGuard halt/win reset
- KillSwitch engage/disengage/guard_write
- RiskQualificationEngine full scenario run
"""

import pytest

from session_smc.risk.guards import (
    DailyLossGuard,
    DrawdownGuard,
    ConsecutiveLossGuard,
    KillSwitch,
)
from session_smc.risk.qualification import RiskQualificationEngine


# ---------------------------------------------------------------------------
# DailyLossGuard
# ---------------------------------------------------------------------------


def test_daily_loss_guard_no_halt_below_limit():
    g = DailyLossGuard(max_daily_loss_r=3.0)
    assert g.check(0.0) is False
    assert g.check(2.99) is False


def test_daily_loss_guard_halts_at_limit():
    g = DailyLossGuard(max_daily_loss_r=3.0)
    assert g.check(3.0) is True


def test_daily_loss_guard_resets():
    g = DailyLossGuard(max_daily_loss_r=3.0)
    g.check(3.0)
    assert g.is_halted is True
    g.reset()
    assert g.is_halted is False
    assert g.check(1.0) is False


# ---------------------------------------------------------------------------
# DrawdownGuard
# ---------------------------------------------------------------------------


def test_drawdown_guard_no_kill_below_threshold():
    g = DrawdownGuard(peak_equity=10_000, max_drawdown_pct=10.0)
    assert g.check(9_500) is False   # -5%
    assert g.check(9_100) is False   # -9%


def test_drawdown_guard_kills_at_threshold():
    g = DrawdownGuard(peak_equity=10_000, max_drawdown_pct=10.0)
    assert g.check(9_000) is True    # exactly -10%


def test_drawdown_guard_updates_peak():
    g = DrawdownGuard(peak_equity=10_000, max_drawdown_pct=10.0)
    g.check(11_000)  # new peak
    assert g.peak_equity == 11_000
    # Now -10% from 11k is 9900 — should not trigger from old 10k base
    assert g.check(9_901) is False
    assert g.check(9_900) is True    # -10% from 11k


# ---------------------------------------------------------------------------
# ConsecutiveLossGuard
# ---------------------------------------------------------------------------


def test_consecutive_loss_guard_no_halt_below():
    g = ConsecutiveLossGuard(max_consecutive_losses=5)
    for _ in range(4):
        g.record_loss()
    assert g.is_halted() is False


def test_consecutive_loss_guard_halts_at_max():
    g = ConsecutiveLossGuard(max_consecutive_losses=5)
    for _ in range(5):
        halted = g.record_loss()
    assert halted is True
    assert g.is_halted() is True


def test_consecutive_loss_win_resets():
    g = ConsecutiveLossGuard(max_consecutive_losses=5)
    for _ in range(5):
        g.record_loss()
    assert g.is_halted() is True
    g.record_win()
    assert g.is_halted() is False
    assert g.count == 0


# ---------------------------------------------------------------------------
# KillSwitch
# ---------------------------------------------------------------------------


def test_kill_switch_starts_disengaged():
    ks = KillSwitch()
    assert ks.is_engaged() is False


def test_kill_switch_engage_blocks_writes():
    ks = KillSwitch()
    ks.engage("Test engagement")
    assert ks.is_engaged() is True
    with pytest.raises(RuntimeError, match="Kill switch is engaged"):
        ks.guard_write()


def test_kill_switch_disengage():
    ks = KillSwitch()
    ks.engage("Test")
    ks.disengage("Operator cleared after review")
    assert ks.is_engaged() is False
    ks.guard_write()  # should not raise


def test_kill_switch_disengage_requires_reason():
    ks = KillSwitch()
    ks.engage("Test")
    with pytest.raises(ValueError):
        ks.disengage("")


# ---------------------------------------------------------------------------
# RiskQualificationEngine
# ---------------------------------------------------------------------------


def test_risk_qualification_engine_passes():
    engine = RiskQualificationEngine(strategy_id="TEST", account_size=10_000)
    report = engine.run_all_scenarios()
    assert report.passed is True, f"Risk qualification failed:\n{report.summary()}"


def test_risk_qualification_report_to_dict():
    engine = RiskQualificationEngine(strategy_id="TEST", account_size=10_000)
    report = engine.run_all_scenarios()
    d = report.to_dict()
    assert d["passed"] is True
    assert d["strategy_id"] == "TEST"
    assert len(d["scenarios"]) > 0


def test_risk_qualification_all_subchecks():
    engine = RiskQualificationEngine(strategy_id="TEST")
    report = engine.run_all_scenarios()
    assert report.position_sizing_ok
    assert report.daily_loss_guard_ok
    assert report.drawdown_guard_ok
    assert report.consecutive_loss_guard_ok
    assert report.kill_switch_ok
    assert report.capital_preservation_ok
