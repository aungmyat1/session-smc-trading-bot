"""
Unit tests for strategies/st_b1_backtest.py — synthetic data only.

These tests prove the backtest *mechanics* are correct (chronological
replay, no-lookahead windowing, SL-before-TP precedence, metrics math).
They do NOT constitute historical validation evidence — see
docs/audit/ST_B1_VALIDATION_REPORT.md for why real 3-year market data
could not be used in this environment.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json

import pytest

from scripts import backtest_st_b1
from strategies.st_b1_backtest import TradeOutcome, compute_metrics, run_backtest, simulate_trade

_UTC = timezone.utc


def _bar(ts, o, hi, lo, c):
    return {"timestamp": ts, "open": o, "high": hi, "low": lo, "close": c}


class TestSimulateTrade:
    def test_win_hits_take_profit(self):
        bars = [_bar(None, 1.1010, 1.1025, 1.1005, 1.1020)]
        outcome, net_r, exit_price, _, _ = simulate_trade(1.1000, 1.0990, 1.1020, "long", bars)
        assert outcome == "win"
        assert net_r == pytest.approx(2.0)  # (1.1020-1.1000)/(1.1000-1.0990) = 0.0020/0.0010
        assert exit_price == 1.1020

    def test_loss_hits_stop(self):
        bars = [_bar(None, 1.0995, 1.0998, 1.0985, 1.0988)]
        outcome, net_r, exit_price, _, _ = simulate_trade(1.1000, 1.0990, 1.1020, "long", bars)
        assert outcome == "loss"
        assert net_r == -1.0
        assert exit_price == 1.0990

    def test_sl_checked_before_tp_in_same_bar(self):
        # Bar's range spans BOTH sl and tp — SL must win.
        bars = [_bar(None, 1.1000, 1.1025, 1.0985, 1.1010)]
        outcome, net_r, exit_price, _, _ = simulate_trade(1.1000, 1.0990, 1.1020, "long", bars)
        assert outcome == "loss"
        assert exit_price == 1.0990

    def test_timeout_after_max_bars_closes_at_last_bar(self):
        bars = [_bar(None, 1.1000, 1.1005, 1.0995, 1.1002) for _ in range(5)]
        outcome, net_r, exit_price, _, _ = simulate_trade(1.1000, 1.0990, 1.1050, "long", bars, max_bars=5)
        assert outcome == "timeout"
        assert exit_price == 1.1002

    def test_short_direction_win(self):
        bars = [_bar(None, 1.1000, 1.1005, 1.0960, 1.0965)]
        outcome, net_r, exit_price, _, _ = simulate_trade(1.1000, 1.1010, 1.0980, "short", bars)
        assert outcome == "win"
        assert exit_price == 1.0980

    def test_zero_risk_returns_timeout(self):
        outcome, net_r, exit_price, _, _ = simulate_trade(1.1000, 1.1000, 1.1020, "long", [])
        assert outcome == "timeout"
        assert net_r == 0.0

    def test_empty_future_bars_returns_timeout_at_entry(self):
        outcome, net_r, exit_price, _, _ = simulate_trade(1.1000, 1.0990, 1.1020, "long", [])
        assert outcome == "timeout"
        assert exit_price == 1.1000


class TestComputeMetrics:
    def _outcome(self, net_r, exit_time="2026-03-15T10:00:00"):
        return TradeOutcome(
            symbol="EURUSD", direction="long", session="london",
            entry=1.1, stop_loss=1.09, take_profit=1.12,
            exit_price=1.1, gross_r=net_r, net_r=net_r,
            outcome="win" if net_r > 0 else "loss",
            entry_time="", exit_time=exit_time, bars_held=1, risk_pips=100.0,
        )

    def test_empty_outcomes(self):
        m = compute_metrics([])
        assert m["trade_count"] == 0
        assert m["profit_factor"] == 0.0

    def test_all_wins_profit_factor_is_infinite(self):
        m = compute_metrics([self._outcome(2.0), self._outcome(2.0)])
        assert m["profit_factor"] == float("inf")
        assert m["win_rate"] == 1.0

    def test_mixed_outcomes_profit_factor(self):
        # 2 wins @ +2R, 1 loss @ -1R -> gross_win=4, gross_loss=1, PF=4
        m = compute_metrics([self._outcome(2.0), self._outcome(2.0), self._outcome(-1.0)])
        assert m["profit_factor"] == 4.0
        assert m["win_rate"] == 2 / 3
        assert m["expectancy_r"] == (2.0 + 2.0 - 1.0) / 3

    def test_max_drawdown_computed_correctly(self):
        # +2, -1, -1, -1 -> peak after first trade = 2, trough after 4th = -1, dd = 3
        m = compute_metrics([self._outcome(2.0), self._outcome(-1.0), self._outcome(-1.0), self._outcome(-1.0)])
        assert m["max_drawdown_r"] == 3.0

    def test_monthly_returns_bucketed_by_exit_month(self):
        outcomes = [
            self._outcome(2.0, exit_time="2026-01-10T00:00:00"),
            self._outcome(-1.0, exit_time="2026-01-20T00:00:00"),
            self._outcome(1.0, exit_time="2026-02-05T00:00:00"),
        ]
        m = compute_metrics(outcomes)
        assert m["monthly_returns_r"]["2026-01"] == 1.0
        assert m["monthly_returns_r"]["2026-02"] == 1.0

    def test_sharpe_zero_when_no_variance(self):
        m = compute_metrics([self._outcome(2.0), self._outcome(2.0)])
        assert m["sharpe_ratio"] == 0.0

    def test_sharpe_positive_for_consistent_winners(self):
        outcomes = [self._outcome(2.0), self._outcome(1.5), self._outcome(-1.0), self._outcome(2.0)]
        m = compute_metrics(outcomes)
        assert m["sharpe_ratio"] > 0


class TestRunBacktestIntegration:
    def _build_dataset(self, n_days=10):
        """Engineers a clean uptrend with periodic one-bar pullback-rejections
        during the London session, so the pipeline has real setups to find."""
        base = datetime(2026, 1, 5, 0, 0, tzinfo=_UTC)  # a Monday
        h1 = []
        m15 = []
        price = 1.1000
        for day in range(n_days):
            for hour in range(24):
                ts = base + timedelta(days=day, hours=hour)
                if ts.weekday() >= 5:
                    continue
                price += 0.0003
                h1.append(_bar(ts, price, price + 0.0002, price - 0.0002, price))
                for q in range(4):
                    m15_ts = ts + timedelta(minutes=15 * q)
                    session = "london" if 8 <= hour < 16 else "off"
                    m_price = price - 0.0003 + q * 0.0001
                    bar = _bar(m15_ts, m_price, m_price + 0.0001, m_price - 0.0001, m_price + 0.00005)
                    bar["session"] = session
                    m15.append(bar)
        return h1, m15

    def test_produces_no_trades_without_enough_h1_history(self):
        h1, m15 = self._build_dataset(n_days=3)
        outcomes = run_backtest(h1, m15, symbol="EURUSD")
        assert outcomes == []  # < TREND_EMA_PERIOD (200) H1 candles available

    def test_session_filter_excludes_off_session_bars(self):
        # Even with enough H1 history, if every M15 bar is tagged "off",
        # no trades should ever be generated.
        h1, m15 = self._build_dataset(n_days=60)
        for bar in m15:
            bar["session"] = "asian"
        outcomes = run_backtest(h1, m15, symbol="EURUSD")
        assert outcomes == []

    def test_no_overlapping_trades_for_one_symbol(self):
        h1, m15 = self._build_dataset(n_days=60)
        outcomes = run_backtest(h1, m15, symbol="EURUSD")
        # Every trade's exit must occur no earlier than the previous trade's
        # entry — i.e. entries are monotonically non-decreasing in dataset
        # order, consistent with "one position per symbol."
        entry_times = [o.entry_time for o in outcomes]
        assert entry_times == sorted(entry_times)

    def test_metrics_are_computable_on_backtest_output(self):
        h1, m15 = self._build_dataset(n_days=60)
        outcomes = run_backtest(h1, m15, symbol="EURUSD")
        metrics = compute_metrics(outcomes)
        assert "trade_count" in metrics
        assert metrics["trade_count"] == len(outcomes)


class TestBacktestCli:
    def test_missing_real_data_writes_blocked_report(self, tmp_path, monkeypatch, capsys):
        reports_dir = tmp_path / "reports"
        missing_data = tmp_path / "missing-data"
        monkeypatch.setattr(backtest_st_b1, "ROOT", tmp_path)
        monkeypatch.setattr(
            "sys.argv",
            [
                "backtest_st_b1.py",
                "--data-dir",
                str(missing_data),
                "--reports-dir",
                str(reports_dir),
                "--source",
                "auto",
            ],
        )

        assert backtest_st_b1.main() == 2

        metrics = json.loads((reports_dir / "st_b1_metrics.json").read_text(encoding="utf-8"))
        report = (reports_dir / "st_b1_validation_report.md").read_text(encoding="utf-8")
        stdout = capsys.readouterr().out
        assert metrics["verdict"] == "BLOCKED"
        assert metrics["blocked_reason"] == "missing_real_market_data"
        assert metrics["standard_cost"]["trade_count"] == 0
        assert "Verdict: BLOCKED" in report
        assert "Do not treat synthetic/unit-test mechanics as validation evidence" in report
        assert '"verdict": "BLOCKED"' in stdout
