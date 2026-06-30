"""
tests/test_risk.py
Lot sizing, daily loss limit, position guard tests for risk.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from smc_bot.risk import (
    calc_qty,
    check_daily_loss_limit,
    check_max_open_positions,
    symbol_already_open,
)
from smc_bot.session_range import SessionSignal

# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

CFG = {
    "instruments": {
        "EURUSD": {
            "pip_size": 0.0001,
            "sl_pct_of_range": 0.25,
            "signal_weight": 1.0,
            "sessions": ["asian", "london"],
            "sweep_beyond_pct": 0.008,
            "atr_period": 14,
            "spread_allowance_pips": 1.0,
        },
        "GBPUSD": {
            "pip_size": 0.0001,
            "sl_pct_of_range": 0.25,
            "signal_weight": 0.9,
            "sessions": ["london"],
            "sweep_beyond_pct": 0.010,
            "atr_period": 14,
            "spread_allowance_pips": 1.5,
        },
        "XAUUSD": {
            "pip_size": 0.01,
            "sl_pct_of_range": 0.20,
            "signal_weight": 1.0,
            "sessions": ["london"],
            "sweep_beyond_pct": 0.005,
            "atr_period": 14,
            "spread_allowance_pips": 3.0,
        },
    },
    "risk": {
        "risk_usd": 100.0,
        "max_lots_per_symbol": 2.0,
        "max_open_positions": 3,
        "max_daily_loss_usd": 150.0,
        "risk_pct_per_trade": 0.01,
    },
}


def _sig(instrument, entry, sl):
    return SessionSignal(
        instrument=instrument,
        session="london",
        setup="sweep",
        side="long" if entry > sl else "short",
        entry=entry,
        sl=sl,
        tp=entry + abs(entry - sl) * 5,
        box_high=entry + 0.005,
        box_low=sl - 0.001,
        signal_weight=1.0,
        mgmt={
            "first_close_pct": 0.75,
            "first_close_target": "opposite_box_edge",
            "trail_remainder": False,
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# calc_qty — EURUSD
# ─────────────────────────────────────────────────────────────────────────────


class TestCalcQtyEURUSD:

    def test_basic_eurusd_lot_sizing(self):
        # risk_usd=100, SL=20 pips, pip_value=$10/lot → expected lots = 100/(20*10) = 0.50
        sig = _sig("EURUSD", entry=1.1020, sl=1.1000)  # 20 pip SL
        lots = calc_qty(sig, CFG, account_balance=10_000)
        assert lots == pytest.approx(0.50, rel=0.05)

    def test_eurusd_caps_at_max_lots(self):
        # Very tight SL → raw lots would exceed max_lots_per_symbol
        sig = _sig("EURUSD", entry=1.1020, sl=1.1019)  # 1 pip SL
        lots = calc_qty(sig, CFG, account_balance=10_000)
        assert lots <= CFG["risk"]["max_lots_per_symbol"]

    def test_eurusd_min_lot_floor(self):
        # Very wide SL → raw lots < MIN_LOT=0.01
        sig = _sig("EURUSD", entry=1.1020, sl=1.0000)  # 1020 pip SL
        lots = calc_qty(sig, CFG, account_balance=10_000)
        assert lots >= 0.01

    def test_eurusd_risk_pct_fallback(self):
        # Remove risk_usd, use risk_pct
        cfg2 = {**CFG, "risk": {**CFG["risk"]}}
        del cfg2["risk"]["risk_usd"]
        sig = _sig("EURUSD", entry=1.1020, sl=1.1000)
        # risk_pct=0.01 * 10000 = $100 → same as risk_usd=100 test above
        lots = calc_qty(sig, cfg2, account_balance=10_000)
        assert lots == pytest.approx(0.50, rel=0.05)


# ─────────────────────────────────────────────────────────────────────────────
# calc_qty — GBPUSD
# ─────────────────────────────────────────────────────────────────────────────


class TestCalcQtyGBPUSD:

    def test_gbpusd_25pip_sl(self):
        # SL=25 pips, risk=$100, pip_value=$10 → 100/(25*10) = 0.40
        sig = _sig("GBPUSD", entry=1.2700, sl=1.2675)
        lots = calc_qty(sig, CFG, account_balance=10_000)
        assert lots == pytest.approx(0.40, rel=0.05)

    def test_gbpusd_rounds_down(self):
        # Ensure rounding is always DOWN (floor), never up
        sig = _sig("GBPUSD", entry=1.2700, sl=1.2657)  # 43 pips → raw=0.2325...
        lots = calc_qty(sig, CFG, account_balance=10_000)
        assert lots == 0.23  # floor to 2 dp


# ─────────────────────────────────────────────────────────────────────────────
# calc_qty — XAUUSD
# ─────────────────────────────────────────────────────────────────────────────


class TestCalcQtyXAUUSD:

    def test_xauusd_200point_sl(self):
        # SL=200 points ($2.00), risk=$100, point_value=$1/lot → 100/(200*1) = 0.50
        sig = _sig("XAUUSD", entry=1920.00, sl=1918.00)  # $2 SL = 200 points
        lots = calc_qty(sig, CFG, account_balance=10_000)
        assert lots == pytest.approx(0.50, rel=0.05)

    def test_xauusd_500point_sl(self):
        # SL=$5.00 → 100/(500*1) = 0.20
        sig = _sig("XAUUSD", entry=1920.00, sl=1915.00)
        lots = calc_qty(sig, CFG, account_balance=10_000)
        assert lots == pytest.approx(0.20, rel=0.05)

    def test_xauusd_caps_at_max_lots(self):
        sig = _sig("XAUUSD", entry=1920.00, sl=1919.99)  # 1 point SL → huge raw lots
        lots = calc_qty(sig, CFG, account_balance=10_000)
        assert lots <= CFG["risk"]["max_lots_per_symbol"]

    def test_xauusd_zero_sl_returns_zero(self):
        sig = _sig("XAUUSD", entry=1920.00, sl=1920.00)  # zero SL
        lots = calc_qty(sig, CFG, account_balance=10_000)
        assert lots == 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Daily loss limit
# ─────────────────────────────────────────────────────────────────────────────


class TestDailyLossLimit:

    def test_limit_not_hit(self):
        assert check_daily_loss_limit(-100.0, CFG) is False

    def test_limit_exactly_hit(self):
        assert check_daily_loss_limit(-150.0, CFG) is True

    def test_limit_exceeded(self):
        assert check_daily_loss_limit(-200.0, CFG) is True

    def test_profit_day_not_hit(self):
        assert check_daily_loss_limit(50.0, CFG) is False


# ─────────────────────────────────────────────────────────────────────────────
# Max open positions
# ─────────────────────────────────────────────────────────────────────────────


class TestMaxOpenPositions:

    def test_under_limit(self):
        positions = [{"id": "p1"}, {"id": "p2"}]
        assert check_max_open_positions(positions, CFG) is False

    def test_at_limit(self):
        positions = [{"id": f"p{i}"} for i in range(3)]
        assert check_max_open_positions(positions, CFG) is True

    def test_over_limit(self):
        positions = [{"id": f"p{i}"} for i in range(5)]
        assert check_max_open_positions(positions, CFG) is True


# ─────────────────────────────────────────────────────────────────────────────
# Symbol already open (one-position-per-instrument rule)
# ─────────────────────────────────────────────────────────────────────────────


class TestSymbolAlreadyOpen:

    def test_symbol_open(self):
        positions = [{"symbol": "EURUSD", "id": "p1"}]
        assert symbol_already_open("EURUSD", positions) is True

    def test_symbol_not_open(self):
        positions = [{"symbol": "XAUUSD", "id": "p1"}]
        assert symbol_already_open("EURUSD", positions) is False

    def test_empty_positions(self):
        assert symbol_already_open("GBPUSD", []) is False

    def test_multiple_symbols_correct_filter(self):
        positions = [
            {"symbol": "EURUSD", "id": "p1"},
            {"symbol": "XAUUSD", "id": "p2"},
        ]
        assert symbol_already_open("GBPUSD", positions) is False
        assert symbol_already_open("EURUSD", positions) is True
