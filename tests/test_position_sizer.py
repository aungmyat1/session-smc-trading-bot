"""Tests for execution/position_sizer.py — lot sizing from risk model."""

import pytest

from execution.position_sizer import _MAX_SL_PIPS, _MIN_SL_PIPS, calculate_lots

# ── Category 1: Standard calculation ─────────────────────────────────────────


class TestStandardCalculation:
    def test_standard_eurusd(self):
        # equity=1000, risk=1%, sl=10pip, pv=10 → risk_amount=10 → lots=10/(10×10)=0.10
        r = calculate_lots(equity=1000.0, sl_pips=10.0, symbol="EURUSD", risk_pct=1.0)
        assert r.valid is True
        assert r.lots == pytest.approx(0.10)
        assert r.risk_amount == pytest.approx(10.0)

    def test_standard_gbpusd(self):
        # GBPUSD uses same pip_value=10 by default
        r = calculate_lots(equity=2000.0, sl_pips=20.0, symbol="GBPUSD", risk_pct=1.0)
        assert r.valid is True
        # 2000×0.01/(20×10) = 20/200 = 0.10
        assert r.lots == pytest.approx(0.10)

    def test_result_fields_populated(self):
        r = calculate_lots(equity=1000.0, sl_pips=10.0, symbol="EURUSD")
        assert r.equity == 1000.0
        assert r.sl_pips == 10.0
        assert r.pip_value == 10.0
        assert r.risk_pct == 1.0
        assert isinstance(r.raw_lots, float)

    def test_different_risk_pct(self):
        # 0.5% risk: equity=2000, sl=10pip → 2000×0.005/(10×10)=1/1=0.10
        r = calculate_lots(equity=2000.0, sl_pips=10.0, symbol="EURUSD", risk_pct=0.5)
        assert r.valid is True
        assert r.lots == pytest.approx(0.10)


# ── Category 2: Floor and clamping ───────────────────────────────────────────


class TestFloorAndClamping:
    def test_floors_not_rounds(self):
        # equity=1000, risk=1%, sl=9pip, pv=10 → 1000×0.01/(9×10)=1/9=0.111…
        # floor(0.111×100)/100 = floor(11.1)/100 = 11/100 = 0.11
        r = calculate_lots(equity=1000.0, sl_pips=9.0, symbol="EURUSD", risk_pct=1.0)
        assert r.valid is True
        assert r.lots == 0.11
        # Confirm it's not rounded up to 0.12
        assert r.lots < r.raw_lots

    def test_minimum_lot_clamped(self):
        # Very high sl_pips → tiny raw_lots → clamped to min_lot
        r = calculate_lots(
            equity=100.0, sl_pips=40.0, symbol="EURUSD", risk_pct=1.0, min_lot=0.01
        )
        # 100×0.01/(40×10)=1/400=0.0025 → floor=0.00 → clamped to 0.01
        assert r.valid is True
        assert r.lots == 0.01
        assert r.clamped is True

    def test_maximum_lot_clamped(self):
        # Very low sl_pips + high equity → lots above max
        r = calculate_lots(
            equity=1_000_000.0, sl_pips=5.0, symbol="EURUSD", risk_pct=1.0, max_lot=10.0
        )
        assert r.valid is True
        assert r.lots == 10.0
        assert r.clamped is True

    def test_not_clamped_for_normal_inputs(self):
        r = calculate_lots(equity=5000.0, sl_pips=10.0, symbol="EURUSD", risk_pct=1.0)
        # 5000×0.01/(10×10)=5/10=0.50
        assert r.clamped is False
        assert r.lots == 0.50


# ── Category 3: SL range validation ──────────────────────────────────────────


class TestSLRangeValidation:
    def test_sl_below_minimum_rejected(self):
        r = calculate_lots(equity=1000.0, sl_pips=2.9, symbol="EURUSD")
        assert r.valid is False
        assert "min" in r.reject_reason
        assert r.lots == 0.0

    def test_sl_exactly_at_minimum_passes(self):
        r = calculate_lots(equity=1000.0, sl_pips=_MIN_SL_PIPS, symbol="EURUSD")
        assert r.valid is True

    def test_sl_above_maximum_rejected(self):
        r = calculate_lots(equity=1000.0, sl_pips=51.0, symbol="EURUSD")
        assert r.valid is False
        assert "max" in r.reject_reason
        assert r.lots == 0.0

    def test_sl_exactly_at_maximum_passes(self):
        r = calculate_lots(equity=1000.0, sl_pips=_MAX_SL_PIPS, symbol="EURUSD")
        assert r.valid is True

    def test_reject_reason_contains_actual_value(self):
        r = calculate_lots(equity=1000.0, sl_pips=1.0, symbol="EURUSD")
        assert "1.0" in r.reject_reason

    def test_st_a2_minimum_five_pip_passes(self):
        # ST-A2 enforces min_sl_pips=5.0 at strategy layer; position_sizer only enforces 3.0
        r = calculate_lots(equity=1000.0, sl_pips=5.0, symbol="EURUSD")
        assert r.valid is True


# ── Category 4: Custom pip value override ────────────────────────────────────


class TestCustomPipValue:
    def test_custom_pip_value_used(self):
        # pip_value_per_lot=5 → 1000×0.01/(10×5)=10/50=0.20
        r = calculate_lots(
            equity=1000.0, sl_pips=10.0, symbol="EXOTIC", pip_value_per_lot=5.0
        )
        assert r.valid is True
        assert r.pip_value == 5.0
        assert r.lots == pytest.approx(0.20)

    def test_unknown_symbol_defaults_to_ten(self):
        r = calculate_lots(equity=1000.0, sl_pips=10.0, symbol="UNKNOWN")
        assert r.pip_value == 10.0
