"""
Unit tests for research/experiments/smc_lss_backtest.py and the
smc_lss_common find_setups() pipeline it drives.

These tests prove pipeline *mechanics* — metrics math, walk-forward
splitting, the BLOCKED-when-no-data path, and no-lookahead — on synthetic
data. They do NOT constitute historical validation evidence; see
docs/audit/SMC_LSS_V0_BACKTEST_REPORT.md for why real EURUSD/GBPUSD/XAUUSD
data could not be used in this environment.
"""

from __future__ import annotations

import json

import pytest

from research.experiments import smc_lss_backtest as bt
from research.experiments.smc_lss_common import find_setups
from strategies.smc_lss.exits import SMCTrade


def _trade(r_multiple, entry_time="2022-06-15T00:00:00Z"):
    return SMCTrade(
        trade_id="t", symbol="EURUSD", branch="combined",
        entry_time=entry_time, exit_time=entry_time,
        entry_price=1.1, exit_price=1.1, direction="long",
        R_multiple=r_multiple, spread=0.0001, MAE=0.0, MFE=max(r_multiple, 0.0),
    )


class TestComputeMetrics:
    def test_empty_trades(self):
        m = bt.compute_metrics([])
        assert m["trade_count"] == 0
        assert m["net_pf"] == 0.0

    def test_pf_and_expectancy(self):
        trades = [_trade(2.0), _trade(2.0), _trade(-1.0)]
        m = bt.compute_metrics(trades)
        assert m["trade_count"] == 3
        assert m["win_count"] == 2
        assert m["net_pf"] == pytest.approx(4.0)  # 4.0 wins / 1.0 losses
        assert m["expectancy_r"] == pytest.approx(1.0)

    def test_max_drawdown(self):
        # running equity: 2.0 (peak=2, dd=0) -> 1.0 (dd=1) -> -3.0 (dd=5) -> -2.0 (dd=4)
        trades = [_trade(2.0), _trade(-1.0), _trade(-4.0), _trade(1.0)]
        m = bt.compute_metrics(trades)
        assert m["max_dd_r"] == pytest.approx(5.0)
        assert m["max_dd_pct"] == pytest.approx(5.0 * bt.ASSUMED_RISK_PCT_PER_TRADE)

    def test_all_losses_pf_zero(self):
        m = bt.compute_metrics([_trade(-1.0), _trade(-0.5)])
        assert m["net_pf"] == 0.0


class TestSplitByPeriod:
    def test_filters_by_entry_date(self):
        trades = [
            _trade(1.0, entry_time="2021-05-01T00:00:00Z"),
            _trade(1.0, entry_time="2024-03-01T00:00:00Z"),
            _trade(1.0, entry_time="2025-07-01T00:00:00Z"),
        ]
        is_trades = bt.split_by_period(trades, "2021-01-01", "2023-12-31")
        oos_trades = bt.split_by_period(trades, "2024-01-01", "2024-12-31")
        forward_trades = bt.split_by_period(trades, "2025-01-01", "2025-12-31")
        assert len(is_trades) == 1
        assert len(oos_trades) == 1
        assert len(forward_trades) == 1

    def test_boundary_dates_inclusive(self):
        trades = [_trade(1.0, entry_time="2023-12-31T23:00:00Z")]
        assert len(bt.split_by_period(trades, "2021-01-01", "2023-12-31")) == 1


class TestLoadSymbolData:
    def test_missing_data_returns_none(self, tmp_path):
        assert bt.load_symbol_data("EURUSD", tmp_path) is None


class TestBlockedRun:
    def test_main_writes_blocked_artifacts_when_data_missing(self, tmp_path, monkeypatch):
        output_dir = tmp_path / "out"
        data_root = tmp_path / "empty_data"
        monkeypatch.setattr(
            "sys.argv",
            ["smc_lss_backtest.py", "--data-root", str(data_root), "--output-dir", str(output_dir)],
        )
        rc = bt.main()
        assert rc == 2

        report = json.loads((output_dir / "performance_report.json").read_text())
        assert report["blocked"] is True
        assert set(report["missing"]) == {"EURUSD", "GBPUSD", "XAUUSD"}
        assert (output_dir / "trade_ledger.parquet").exists()
        assert (output_dir / "equity_curve.csv").exists()
        assert (output_dir / "drawdown_report.json").exists()


# ── No-lookahead pipeline test (synthetic full-chain scenario) ────────────
#
# Uses deliberately small lookback windows (structure_lookback=3,
# swing_lookback=3, atr_period=3, inducement_window=3, displacement_body_atr=1.0)
# so a complete sweep -> CHoCH -> inducement -> displacement -> FVG-pullback
# chain can be hand-constructed in ~14 bars. This is NOT the production
# config/strategies/SMC-LSS_v0.yaml default (swing_lookback=10 etc.) — see
# strategies/smc_lss/{liquidity,structure,displacement}.py unit tests for
# threshold-accurate coverage of the production defaults.

_TEST_CFG = {
    "swing_lookback": 3,
    "sweep_atr_threshold": 0.1,
    "structure_lookback": 3,
    "inducement_window": 3,
    "displacement_body_atr": 1.0,
    "atr_period": 3,
}


def _m5_bar(idx, o, h, l, c):
    return {"timestamp": f"2024-01-02T00:{idx:02d}:00Z", "open": o, "high": h, "low": l, "close": c}


def _build_synthetic_chain():
    flat = [_m5_bar(i, 1.1000, 1.1006, 1.0994, 1.1000) for i in range(6)]
    m5 = flat + [
        _m5_bar(6, 1.1000, 1.1005, 1.0980, 1.1002),   # bullish sweep (swept_level=1.0994)
        _m5_bar(7, 1.1002, 1.1008, 1.0998, 1.1004),
        _m5_bar(8, 1.1004, 1.1010, 1.1000, 1.1006),
        _m5_bar(9, 1.1006, 1.1034, 1.1004, 1.1032),   # CHoCH confirm + displacement candle
        _m5_bar(10, 1.1030, 1.1040, 1.1020, 1.1035),  # closes FVG's "after" leg
        _m5_bar(11, 1.1035, 1.1038, 1.1015, 1.1030),  # pullback into FVG [1.1010, 1.1020]
        _m5_bar(12, 1.1030, 1.1034, 1.1026, 1.1030),
        _m5_bar(13, 1.1030, 1.1034, 1.1026, 1.1030),
    ]
    d1 = [
        {"timestamp": "2024-01-01T00:00:00Z", "open": 1.0950, "high": 1.1000, "low": 1.0940, "close": 1.0990},
        {"timestamp": "2024-01-02T00:00:00Z", "open": 1.1000, "high": 1.1050, "low": 1.0990, "close": 1.1040},
    ]
    h1: list = []
    return m5, d1, h1


class TestFindSetupsNoLookahead:
    def test_expected_setup_detected(self):
        m5, d1, h1 = _build_synthetic_chain()
        setups = find_setups(m5, d1, h1, symbol="EURUSD", cfg=_TEST_CFG)
        matches = [s for s in setups if s.displacement_index == 9]
        assert len(matches) == 1
        setup = matches[0]
        assert setup.direction == "long"
        assert setup.choch.broken_level == pytest.approx(1.1010)
        assert setup.shift.pullback_index == 11
        assert setup.shift.fvg_low == pytest.approx(1.1010)
        assert setup.shift.fvg_high == pytest.approx(1.1020)

    def test_truncating_data_after_pullback_reproduces_same_setup(self):
        """The setup must be fully determined by data through its own
        pullback bar — extending the dataset further must not be required
        to detect it (no lookahead)."""
        m5, d1, h1 = _build_synthetic_chain()
        setups_full = find_setups(m5, d1, h1, symbol="EURUSD", cfg=_TEST_CFG)
        target = next(s for s in setups_full if s.displacement_index == 9)

        truncated = m5[: target.shift.pullback_index + 1]
        setups_truncated = find_setups(truncated, d1, h1, symbol="EURUSD", cfg=_TEST_CFG)
        matches = [s for s in setups_truncated if s.displacement_index == 9]

        assert len(matches) == 1
        assert matches[0].shift.pullback_index == target.shift.pullback_index
        assert matches[0].choch.broken_level == target.choch.broken_level

    def test_truncating_data_before_pullback_finds_no_setup(self):
        """Before the pullback bar has closed, the setup must not yet be
        detectable — proves the pipeline isn't retroactively inferring it."""
        m5, d1, h1 = _build_synthetic_chain()
        truncated = m5[:11]  # ends right before the pullback bar (index 11)
        setups = find_setups(truncated, d1, h1, symbol="EURUSD", cfg=_TEST_CFG)
        assert [s for s in setups if s.displacement_index == 9] == []
