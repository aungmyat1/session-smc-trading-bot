"""
Tests for scripts/backtest_session_liquidity.py — pure functions only.
I/O (CSV loading, file writing, research logging) is not tested here.
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

from scripts.backtest_session_liquidity import (
    simulate_trade,
    spread_cost_r,
    compute_metrics,
    max_drawdown,
    extract_contexts,
    build_time_index,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _bar(time, high, low, open_=None, close=None):
    o = open_ if open_ is not None else (high + low) / 2
    c = close if close is not None else (high + low) / 2
    return {"time": time, "open": o, "high": high, "low": low, "close": c, "volume": 0.0}


def _long_bars():
    """Long setup: entry=1.0700, sl=1.0680, risk=20pip, rr=3 → tp=1.0760."""
    entry, sl = 1.0700, 1.0680
    return entry, sl, "long"


def _short_bars():
    """Short setup: entry=1.0700, sl=1.0730, risk=30pip, rr=3 → tp=1.0610."""
    entry, sl = 1.0700, 1.0730
    return entry, sl, "short"


# ── simulate_trade ────────────────────────────────────────────────────────────

class TestSimulateTrade:

    def test_long_win_on_tp_hit(self):
        entry, sl, side = _long_bars()
        rr = 3.0
        risk = abs(entry - sl)
        tp = entry + risk * rr
        bars = [_bar("t1", high=tp + 0.001, low=1.0705)]
        outcome, gross_r, exit_p, _, bars_held = simulate_trade(entry, sl, side, rr, bars)
        assert outcome == "win"
        assert gross_r == rr
        assert exit_p == tp
        assert bars_held == 1

    def test_long_loss_on_sl_hit(self):
        entry, sl, side = _long_bars()
        bars = [_bar("t1", high=1.0710, low=sl - 0.001)]
        outcome, gross_r, exit_p, _, bars_held = simulate_trade(entry, sl, side, 3.0, bars)
        assert outcome == "loss"
        assert gross_r == -1.0
        assert exit_p == sl
        assert bars_held == 1

    def test_long_sl_before_tp_same_bar(self):
        """When SL and TP both in same bar, SL wins (spec rule)."""
        entry, sl, side = _long_bars()
        rr = 3.0
        risk = abs(entry - sl)
        tp = entry + risk * rr
        bars = [_bar("t1", high=tp + 0.001, low=sl - 0.001)]
        outcome, gross_r, _, _, _ = simulate_trade(entry, sl, side, rr, bars)
        assert outcome == "loss"
        assert gross_r == -1.0

    def test_short_win_on_tp_hit(self):
        entry, sl, side = _short_bars()
        rr = 2.0
        risk = abs(entry - sl)
        tp = entry - risk * rr
        bars = [_bar("t1", high=1.0710, low=tp - 0.001)]
        outcome, gross_r, exit_p, _, _ = simulate_trade(entry, sl, side, rr, bars)
        assert outcome == "win"
        assert gross_r == rr
        assert exit_p == tp

    def test_short_loss_on_sl_hit(self):
        entry, sl, side = _short_bars()
        bars = [_bar("t1", high=sl + 0.001, low=1.0690)]
        outcome, gross_r, _, _, _ = simulate_trade(entry, sl, side, 3.0, bars)
        assert outcome == "loss"
        assert gross_r == -1.0

    def test_short_sl_before_tp_same_bar(self):
        entry, sl, side = _short_bars()
        rr = 3.0
        risk = abs(entry - sl)
        tp = entry - risk * rr
        bars = [_bar("t1", high=sl + 0.001, low=tp - 0.001)]
        outcome, _, _, _, _ = simulate_trade(entry, sl, side, rr, bars)
        assert outcome == "loss"

    def test_timeout_returns_fractional_r(self):
        entry, sl, side = _long_bars()
        risk = abs(entry - sl)
        exit_close = entry + risk * 1.5  # halfway to 3R
        bars = [_bar(f"t{i}", high=entry + 0.0001, low=entry - 0.0001, close=exit_close)
                for i in range(96)]
        outcome, gross_r, exit_p, _, bars_held = simulate_trade(entry, sl, side, 3.0, bars)
        assert outcome == "timeout"
        assert abs(gross_r - 1.5) < 1e-9
        assert bars_held == 96

    def test_timeout_at_max_bars_cap(self):
        """Extra bars beyond max_bars=96 are ignored."""
        entry, sl, side = _long_bars()
        bars = [_bar(f"t{i}", high=entry + 0.0001, low=entry - 0.0001)
                for i in range(200)]
        _, _, _, _, bars_held = simulate_trade(entry, sl, side, 3.0, bars, max_bars=96)
        assert bars_held == 96

    def test_timeout_with_fewer_than_max_bars(self):
        entry, sl, side = _long_bars()
        bars = [_bar(f"t{i}", high=entry + 0.0001, low=entry - 0.0001) for i in range(10)]
        outcome, _, _, _, bars_held = simulate_trade(entry, sl, side, 3.0, bars)
        assert outcome == "timeout"
        assert bars_held == 10

    def test_zero_risk_returns_timeout(self):
        """entry == sl → risk=0 → immediate timeout."""
        outcome, gross_r, _, _, _ = simulate_trade(1.0700, 1.0700, "long", 3.0, [])
        assert outcome == "timeout"
        assert gross_r == 0.0

    def test_empty_bars_timeout(self):
        outcome, gross_r, exit_p, exit_t, bars_held = simulate_trade(
            1.0700, 1.0680, "long", 3.0, []
        )
        assert outcome == "timeout"
        assert gross_r == 0.0
        assert bars_held == 0

    def test_win_reached_on_second_bar(self):
        entry, sl, side = _long_bars()
        rr = 2.0
        risk = abs(entry - sl)
        tp = entry + risk * rr
        bars = [
            _bar("t1", high=entry + 0.0005, low=entry - 0.0005),
            _bar("t2", high=tp + 0.001, low=entry),
        ]
        outcome, gross_r, _, _, bars_held = simulate_trade(entry, sl, side, rr, bars)
        assert outcome == "win"
        assert gross_r == rr
        assert bars_held == 2

    def test_short_timeout_fractional_r(self):
        entry, sl, side = _short_bars()
        risk = abs(entry - sl)
        exit_close = entry - risk * 1.0  # exactly 1R profit direction
        bars = [_bar(f"t{i}", high=entry + 0.0001, low=entry - 0.0001, close=exit_close)
                for i in range(96)]
        outcome, gross_r, _, _, _ = simulate_trade(entry, sl, side, 3.0, bars)
        assert outcome == "timeout"
        assert abs(gross_r - 1.0) < 1e-9

    def test_custom_max_bars(self):
        """max_bars override stops at the custom limit."""
        entry, sl, side = _long_bars()
        bars = [_bar(f"t{i}", high=entry + 0.0001, low=entry - 0.0001) for i in range(50)]
        _, _, _, _, bars_held = simulate_trade(entry, sl, side, 3.0, bars, max_bars=20)
        assert bars_held == 20

    def test_rr_variants_produce_different_tps(self):
        entry, sl, side = _long_bars()
        risk = abs(entry - sl)
        for rr in [2.0, 3.0, 4.0, 5.0]:
            tp = entry + risk * rr
            bars_hit  = [_bar("t1", high=tp + 0.0001, low=entry - 0.0001)]
            bars_miss = [_bar("t1", high=tp - 0.0001, low=entry - 0.0001)]
            outcome_hit,  _, _, _, _ = simulate_trade(entry, sl, side, rr, bars_hit)
            outcome_miss, _, _, _, _ = simulate_trade(entry, sl, side, rr, bars_miss)
            assert outcome_hit  == "win",    f"rr={rr}: expected win"
            assert outcome_miss != "win",    f"rr={rr}: should not win yet"


# ── spread_cost_r ─────────────────────────────────────────────────────────────

class TestSpreadCostR:

    def test_basic_eurusd(self):
        # 1.4 pip std spread / 20 pip SL
        cost = spread_cost_r(1.4, 20.0)
        assert abs(cost - 0.07) < 1e-9

    def test_basic_gbpusd_standard(self):
        cost = spread_cost_r(1.8, 24.0)
        assert abs(cost - 0.075) < 1e-9

    def test_2x_stress(self):
        # 2.8 pip 2× / 20 pip SL
        cost = spread_cost_r(2.8, 20.0)
        assert abs(cost - 0.14) < 1e-9

    def test_zero_sl_returns_zero(self):
        assert spread_cost_r(1.4, 0.0) == 0.0

    def test_negative_sl_returns_zero(self):
        assert spread_cost_r(1.4, -5.0) == 0.0

    def test_larger_sl_smaller_cost(self):
        cost_small_sl = spread_cost_r(1.4, 10.0)
        cost_large_sl = spread_cost_r(1.4, 40.0)
        assert cost_small_sl > cost_large_sl


# ── compute_metrics ───────────────────────────────────────────────────────────

class TestComputeMetrics:

    def test_empty_returns_zeros(self):
        m = compute_metrics([])
        assert m["trade_count"] == 0
        assert m["net_pf"] == 0.0

    def test_all_wins(self):
        # 3 wins at 3R each → PF = inf, win_rate = 100%
        m = compute_metrics([3.0, 3.0, 3.0])
        assert m["trade_count"] == 3
        assert m["win_count"] == 3
        assert m["loss_count"] == 0
        assert m["win_rate"] == 1.0
        assert m["net_pf"] == float("inf")

    def test_all_losses(self):
        m = compute_metrics([-1.0, -1.0, -1.0])
        assert m["trade_count"] == 3
        assert m["win_count"] == 0
        assert m["loss_count"] == 3
        assert m["net_pf"] == 0.0
        assert m["win_rate"] == 0.0

    def test_mixed_win_loss(self):
        # 2 wins @ 3R, 3 losses @ -1R → gross_wins=6, gross_losses=3 → PF=2.0
        rs = [3.0, 3.0, -1.0, -1.0, -1.0]
        m = compute_metrics(rs)
        assert abs(m["net_pf"] - 2.0) < 1e-9
        assert abs(m["win_rate"] - 0.4) < 1e-9
        assert abs(m["avg_r"] - 0.6) < 1e-9

    def test_total_net_r(self):
        rs = [2.5, -1.0, 3.0, -1.0]
        m = compute_metrics(rs)
        assert abs(m["total_net_r"] - 3.5) < 1e-9

    def test_avg_r(self):
        rs = [2.0, -1.0, 4.0, -1.0]
        m = compute_metrics(rs)
        assert abs(m["avg_r"] - 1.0) < 1e-9

    def test_pf_greater_than_one_passes_gate(self):
        rs = [2.9, 2.9, -1.07, -1.07, -1.07]  # spread-applied values
        m = compute_metrics(rs)
        assert m["net_pf"] > 1.0

    def test_fractional_timeout_counted(self):
        rs = [1.5, -1.07, 0.8, -1.07]
        m = compute_metrics(rs)
        assert m["trade_count"] == 4

    def test_zero_r_is_loss_side(self):
        m = compute_metrics([0.0])
        assert m["win_count"] == 0
        assert m["loss_count"] == 1

    def test_count_matches_input(self):
        rs = list(range(-5, 6))  # -5..5
        m = compute_metrics(rs)
        assert m["trade_count"] == 11


# ── max_drawdown ──────────────────────────────────────────────────────────────

class TestMaxDrawdown:

    def test_empty(self):
        assert max_drawdown([]) == 0.0

    def test_all_wins_no_drawdown(self):
        assert max_drawdown([1.0, 2.0, 3.0]) == 0.0

    def test_all_losses(self):
        # cumulative: -1, -2, -3 — peak stays 0, DD grows to 3
        assert abs(max_drawdown([-1.0, -1.0, -1.0]) - 3.0) < 1e-9

    def test_win_then_loss(self):
        # +3, -1 → peak=3, then 2 → dd=1
        assert abs(max_drawdown([3.0, -1.0]) - 1.0) < 1e-9

    def test_multiple_drawdown_periods(self):
        # +3, -2 (dd=2), +4 (peak=5), -3 (dd=3 ← bigger)
        assert abs(max_drawdown([3.0, -2.0, 4.0, -3.0]) - 3.0) < 1e-9

    def test_single_big_loss_is_drawdown(self):
        assert abs(max_drawdown([-5.0]) - 5.0) < 1e-9

    def test_recovers_fully(self):
        # -3, +3 — peak=0, dd=3, then recovers to 0; max_dd=3
        assert abs(max_drawdown([-3.0, 3.0]) - 3.0) < 1e-9


# ── extract_contexts ──────────────────────────────────────────────────────────

class TestExtractContexts:

    def _make_event(self, date, etype, detail):
        return {"date": date, "event": etype, "detail": detail}

    def test_asian_range_parsed(self):
        ev = self._make_event(
            "2023-03-14", "ASIAN_RANGE",
            "H=1.07309 L=1.06970 range=33.9pip"
        )
        asian, _ = extract_contexts([ev])
        assert "2023-03-14" in asian
        ar = asian["2023-03-14"]
        assert abs(ar["high"] - 1.07309) < 1e-5
        assert abs(ar["low"] - 1.06970) < 1e-5
        assert abs(ar["range_pips"] - 33.9) < 0.01

    def test_sweep_parsed(self):
        ev = self._make_event(
            "2023-03-14", "SWEEP",
            "[08:00 UTC] london side=long price=1.06878 bias=bullish"
        )
        _, sweeps = extract_contexts([ev])
        assert ("2023-03-14", "london") in sweeps
        sw = sweeps[("2023-03-14", "london")]
        assert sw["bias"] == "bullish"
        assert sw["time_iso"] == "2023-03-14T08:00:00Z"

    def test_later_sweep_overwrites_earlier(self):
        evs = [
            self._make_event("2023-03-14", "SWEEP",
                             "[06:15 UTC] london side=long price=1.06942 bias=bullish"),
            self._make_event("2023-03-14", "SWEEP",
                             "[08:00 UTC] london side=long price=1.06878 bias=bullish"),
        ]
        _, sweeps = extract_contexts(evs)
        sw = sweeps[("2023-03-14", "london")]
        assert sw["time_iso"] == "2023-03-14T08:00:00Z"

    def test_different_sessions_separate(self):
        evs = [
            self._make_event("2023-03-14", "SWEEP",
                             "[08:00 UTC] london side=long price=1.0 bias=bullish"),
            self._make_event("2023-03-14", "SWEEP",
                             "[13:00 UTC] new_york side=long price=1.1 bias=bullish"),
        ]
        _, sweeps = extract_contexts(evs)
        assert ("2023-03-14", "london") in sweeps
        assert ("2023-03-14", "new_york") in sweeps

    def test_non_event_types_ignored(self):
        evs = [
            self._make_event("2023-03-14", "NO_SWEEP", "some detail"),
            self._make_event("2023-03-14", "SIGNAL", "[08:45 UTC] london long"),
            self._make_event("2023-03-14", "SKIP_DAY", "range too small"),
        ]
        asian, sweeps = extract_contexts(evs)
        assert len(asian) == 0
        assert len(sweeps) == 0

    def test_bearish_sweep_bias(self):
        ev = self._make_event(
            "2024-06-05", "SWEEP",
            "[14:00 UTC] new_york side=short price=1.0850 bias=bearish"
        )
        _, sweeps = extract_contexts([ev])
        sw = sweeps[("2024-06-05", "new_york")]
        assert sw["bias"] == "bearish"

    def test_multiple_dates(self):
        evs = [
            self._make_event("2023-03-14", "ASIAN_RANGE", "H=1.073 L=1.069 range=40.0pip"),
            self._make_event("2023-03-15", "ASIAN_RANGE", "H=1.080 L=1.075 range=50.0pip"),
        ]
        asian, _ = extract_contexts(evs)
        assert len(asian) == 2
        assert "2023-03-14" in asian
        assert "2023-03-15" in asian

    def test_empty_events(self):
        asian, sweeps = extract_contexts([])
        assert asian == {}
        assert sweeps == {}


# ── build_time_index ──────────────────────────────────────────────────────────

class TestBuildTimeIndex:

    def test_maps_time_to_index(self):
        bars = [
            {"time": "2023-03-14T06:00:00Z", "open": 1.0, "high": 1.1, "low": 0.9, "close": 1.0, "volume": 0},
            {"time": "2023-03-14T06:15:00Z", "open": 1.0, "high": 1.1, "low": 0.9, "close": 1.0, "volume": 0},
            {"time": "2023-03-14T06:30:00Z", "open": 1.0, "high": 1.1, "low": 0.9, "close": 1.0, "volume": 0},
        ]
        idx = build_time_index(bars)
        assert idx["2023-03-14T06:00:00Z"] == 0
        assert idx["2023-03-14T06:15:00Z"] == 1
        assert idx["2023-03-14T06:30:00Z"] == 2

    def test_unknown_time_not_in_index(self):
        bars = [{"time": "2023-03-14T06:00:00Z", "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 0}]
        idx = build_time_index(bars)
        assert "2023-03-14T07:00:00Z" not in idx

    def test_empty_bars(self):
        assert build_time_index([]) == {}
