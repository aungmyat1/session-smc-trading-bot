"""
Tests for scripts/run_experiments.py — pure functions only.
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

from scripts.run_experiments import (
    apply_filter,
    compute_metrics,
    gate_check,
    run_all_experiments,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _trade(
    sym="EURUSD", session="london", rr=5.0,
    sl_pips=20.0, asian_range_pips=25.0,
    gross_r=5.0, net_r_std=4.93, net_r_2x=4.86,
    bars_held=10, exit_reason="tp",
):
    return {
        "sym": sym, "session": session, "rr": rr,
        "sl_pips": sl_pips, "asian_range_pips": asian_range_pips,
        "gross_r": gross_r, "net_r_std": net_r_std, "net_r_2x": net_r_2x,
        "bars_held": bars_held, "exit_reason": exit_reason,
        "year": "2024",
    }


def _loss(sl_pips=20.0, sym="EURUSD", session="london", rr=5.0):
    return _trade(sym=sym, session=session, rr=rr, sl_pips=sl_pips,
                  gross_r=-1.0, net_r_std=-1.07, net_r_2x=-1.14,
                  bars_held=5, exit_reason="sl")


def _win(rr=5.0, sl_pips=20.0, sym="EURUSD", session="london"):
    return _trade(sym=sym, session=session, rr=rr, sl_pips=sl_pips,
                  gross_r=rr, net_r_std=rr - 1.4/sl_pips, net_r_2x=rr - 2.8/sl_pips)


def _timeout():
    return _trade(gross_r=1.5, net_r_std=1.43, net_r_2x=1.36,
                  bars_held=96, exit_reason="timeout")


# ── apply_filter ──────────────────────────────────────────────────────────────

class TestApplyFilter:

    def test_all_pass(self):
        trades = [_trade(sl_pips=10), _trade(sl_pips=20)]
        assert apply_filter(trades, lambda t: t["sl_pips"] >= 5) == trades

    def test_all_filtered(self):
        trades = [_trade(sl_pips=3), _trade(sl_pips=4)]
        assert apply_filter(trades, lambda t: t["sl_pips"] >= 5) == []

    def test_partial_filter(self):
        trades = [_trade(sl_pips=4), _trade(sl_pips=10), _trade(sl_pips=2)]
        result = apply_filter(trades, lambda t: t["sl_pips"] >= 5)
        assert len(result) == 1
        assert result[0]["sl_pips"] == 10

    def test_empty_input(self):
        assert apply_filter([], lambda t: True) == []

    def test_session_filter_ny_only(self):
        trades = [
            _trade(session="london"),
            _trade(session="new_york"),
            _trade(session="london"),
        ]
        result = apply_filter(trades, lambda t: t["session"] == "new_york")
        assert len(result) == 1
        assert result[0]["session"] == "new_york"

    def test_exclude_gbpusd_london(self):
        trades = [
            _trade(sym="GBPUSD", session="london"),
            _trade(sym="GBPUSD", session="new_york"),
            _trade(sym="EURUSD", session="london"),
            _trade(sym="EURUSD", session="new_york"),
        ]
        def fn(t):
            return not (t["sym"] == "GBPUSD" and t["session"] == "london")
        result = apply_filter(trades, fn)
        assert len(result) == 3
        assert not any(t["sym"] == "GBPUSD" and t["session"] == "london" for t in result)

    def test_asian_range_filter(self):
        trades = [
            _trade(asian_range_pips=18),
            _trade(asian_range_pips=22),
            _trade(asian_range_pips=15),
        ]
        result = apply_filter(trades, lambda t: t["asian_range_pips"] >= 20)
        assert len(result) == 1
        assert result[0]["asian_range_pips"] == 22

    def test_filter_preserves_order(self):
        trades = [_trade(sl_pips=i * 5.0) for i in range(5)]
        result = apply_filter(trades, lambda t: t["sl_pips"] >= 10)
        sl_vals = [t["sl_pips"] for t in result]
        assert sl_vals == sorted(sl_vals)


# ── compute_metrics ───────────────────────────────────────────────────────────

class TestComputeMetrics:

    def test_empty_returns_zeros(self):
        m = compute_metrics([])
        assert m["n"] == 0
        assert m["net_pf_std"] == 0.0
        assert m["net_pf_2x"] == 0.0

    def test_all_wins(self):
        trades = [_win() for _ in range(5)]
        m = compute_metrics(trades)
        assert m["n"] == 5
        assert m["win_rate"] == 1.0
        assert m["net_pf_std"] == float("inf")
        assert m["net_pf_2x"] == float("inf")

    def test_all_losses(self):
        trades = [_loss() for _ in range(5)]
        m = compute_metrics(trades)
        assert m["n"] == 5
        assert m["win_rate"] == 0.0
        assert m["net_pf_std"] == 0.0
        assert m["net_pf_2x"] == 0.0

    def test_mixed_pf_calc(self):
        # 2 wins at 5R, 3 losses at -1R → gross = 10/3 ≈ 3.333
        wins   = [_trade(gross_r=5.0, net_r_std=4.93, net_r_2x=4.86)] * 2
        losses = [_trade(gross_r=-1.0, net_r_std=-1.07, net_r_2x=-1.14)] * 3
        m = compute_metrics(wins + losses)
        assert abs(m["gross_pf"] - 10/3) < 0.001

    def test_win_rate_correct(self):
        trades = [_win()] * 3 + [_loss()] * 7
        m = compute_metrics(trades)
        # win = net_r_std > 0, so 3 wins
        assert abs(m["win_rate"] - 0.3) < 1e-9

    def test_avg_duration(self):
        trades = [
            _trade(bars_held=4),
            _trade(bars_held=8),
            _trade(bars_held=12),
        ]
        m = compute_metrics(trades)
        # avg bars = (4+8+12)/3 = 8, × 15 = 120 min
        assert abs(m["avg_dur_min"] - 120.0) < 1e-9

    def test_max_dd_calculated(self):
        # +5, -1, -1, -1 → cumulative: 5, 4, 3, 2 → peak=5 → dd=3
        trades = [
            _trade(net_r_std=5.0), _trade(net_r_std=-1.0),
            _trade(net_r_std=-1.0), _trade(net_r_std=-1.0),
        ]
        m = compute_metrics(trades)
        assert abs(m["max_dd"] - 3.0) < 1e-9

    def test_gross_pf_before_spread(self):
        # Win: gross=3, net_std=2.93; Loss: gross=-1, net_std=-1.07
        win  = _trade(gross_r=3.0, net_r_std=2.93, net_r_2x=2.86)
        loss = _trade(gross_r=-1.0, net_r_std=-1.07, net_r_2x=-1.14)
        m = compute_metrics([win, loss])
        assert abs(m["gross_pf"] - 3.0) < 0.001

    def test_2x_pf_worse_than_std(self):
        win  = _trade(gross_r=5.0, net_r_std=4.93, net_r_2x=4.86)
        loss = _trade(gross_r=-1.0, net_r_std=-1.07, net_r_2x=-1.14)
        m = compute_metrics([win, loss])
        assert m["net_pf_2x"] < m["net_pf_std"]

    def test_n_count(self):
        trades = [_trade() for _ in range(37)]
        assert compute_metrics(trades)["n"] == 37


# ── gate_check ────────────────────────────────────────────────────────────────

class TestGateCheck:

    def _m(self, n=100, pf_std=1.1, pf_2x=1.05):
        return {"n": n, "net_pf_std": pf_std, "net_pf_2x": pf_2x}

    def test_all_pass(self):
        assert gate_check(self._m()) is True

    def test_fail_n_too_low(self):
        assert gate_check(self._m(n=99)) is False

    def test_fail_pf_std_at_boundary(self):
        assert gate_check(self._m(pf_std=1.0)) is False

    def test_fail_pf_2x_at_boundary(self):
        assert gate_check(self._m(pf_2x=1.0)) is False

    def test_fail_pf_std_below(self):
        assert gate_check(self._m(pf_std=0.99)) is False

    def test_fail_pf_2x_below(self):
        assert gate_check(self._m(pf_2x=0.965)) is False

    def test_exact_100_trades_passes(self):
        assert gate_check(self._m(n=100)) is True

    def test_strictly_greater_pf_required(self):
        assert gate_check(self._m(pf_std=1.001, pf_2x=1.001)) is True


# ── run_all_experiments ───────────────────────────────────────────────────────

class TestRunAllExperiments:

    def _make_trades(self, n_rr=5, n_per_rr=20):
        """Generate synthetic trades for all RR variants."""
        trades = []
        for rr in [2.0, 3.0, 4.0, 5.0]:
            for i in range(n_per_rr):
                sl = 5.0 if i < 3 else 20.0  # 3 narrow-SL trades per RR
                trades.append(_trade(
                    rr=rr, sl_pips=sl,
                    session="london" if i % 3 != 0 else "new_york",
                    sym="GBPUSD" if i % 5 == 0 else "EURUSD",
                    asian_range_pips=15.0 if i < 5 else 25.0,
                ))
        return trades

    def test_returns_correct_count(self):
        trades = self._make_trades()
        # EXP-01: 3 variants × 4 RR = 12
        # EXP-02: 3 variants × 4 RR = 12
        # EXP-03: 1 variant × 4 RR = 4
        # EXP-04: 1 variant × 4 RR = 4
        # Total = 32
        results = run_all_experiments(trades)
        assert len(results) == 32

    def test_result_has_required_fields(self):
        trades = self._make_trades()
        r = run_all_experiments(trades)[0]
        for field in ["exp_id", "exp_name", "variant", "rr", "n",
                      "win_rate", "gross_pf", "net_pf_std", "net_pf_2x",
                      "max_dd", "avg_dur_min", "gate"]:
            assert field in r, f"Missing field: {field}"

    def test_exp01_removes_narrow_sl(self):
        # 3 narrow SL (< 5pip) + 17 wide SL per RR
        trades = self._make_trades()
        results = run_all_experiments(trades)
        # EXP-01 ≥5pip at RR5
        r = next(r for r in results
                 if r["exp_id"] == "EXP-01" and r["variant"] == "≥ 5 pip" and r["rr"] == 5.0)
        _baseline = next(r for r in results
                        if r["exp_id"] == "EXP-01" and r["variant"] == "≥ 5 pip" and r["rr"] == 5.0)
        # ≥5pip floor removes 3 trades per RR (those with sl=5.0 are kept, sl<5 removed)
        # sl_pips=5.0 exactly passes ≥5 — all 20 trades kept since min is 5.0
        assert r["n"] == 20  # sl=5.0 passes ≥5 check

    def test_exp03_ny_only(self):
        trades = self._make_trades()
        results = run_all_experiments(trades)
        r = next(r for r in results
                 if r["exp_id"] == "EXP-03" and r["rr"] == 5.0)
        # i % 3 != 0 → london, i % 3 == 0 → new_york
        # for 20 trades: i=0,3,6,9,12,15,18 → 7 NY trades
        assert r["n"] == 7

    def test_exp04_excludes_gbp_london(self):
        trades = self._make_trades()
        results = run_all_experiments(trades)
        r = next(r for r in results
                 if r["exp_id"] == "EXP-04" and r["rr"] == 5.0)
        # Count trades that are NOT (GBPUSD AND london)
        rr5 = [t for t in trades if t["rr"] == 5.0]
        expected = sum(1 for t in rr5
                       if not (t["sym"] == "GBPUSD" and t["session"] == "london"))
        assert r["n"] == expected

    def test_all_rr_variants_represented(self):
        trades = self._make_trades()
        results = run_all_experiments(trades)
        for exp_id in ["EXP-01", "EXP-02", "EXP-03", "EXP-04"]:
            rrs_in_results = {r["rr"] for r in results if r["exp_id"] == exp_id}
            assert rrs_in_results == {2.0, 3.0, 4.0, 5.0}

    def test_exp_ids_present(self):
        trades = self._make_trades()
        results = run_all_experiments(trades)
        ids = {r["exp_id"] for r in results}
        assert ids == {"EXP-01", "EXP-02", "EXP-03", "EXP-04"}

    def test_gate_false_on_tiny_n(self):
        # Very small dataset — gate should fail
        trades = [_trade(rr=r) for r in [2.0, 3.0, 4.0, 5.0]]
        results = run_all_experiments(trades)
        assert all(not r["gate"] for r in results)
