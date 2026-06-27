from __future__ import annotations

from research.robustness import (
    monte_carlo_resampling,
    parameter_sensitivity,
    regime_analysis,
    walk_forward_analysis,
)


def _trades() -> list[dict[str, object]]:
    values = [0.8, 0.2, 0.1, 0.7, 0.3, 0.1, 0.9, 0.25, 0.15, 0.6, 0.4, 0.2]
    trades: list[dict[str, object]] = []
    for idx, value in enumerate(values, start=1):
        trades.append(
            {
                "trade_id": f"T{idx}",
                "entry_time": f"2026-06-{idx:02d}T08:00:00Z",
                "session": "London" if idx <= 6 else "New York",
                "regime": "trend" if idx % 2 else "mean_revert",
                "std_net_r": value,
            }
        )
    return trades


def test_walk_forward_analysis_is_deterministic():
    trades = _trades()
    first = walk_forward_analysis(trades, folds=4)
    second = walk_forward_analysis(trades, folds=4)
    assert first == second
    assert first["passed"] is True
    assert len(first["folds"]) == 4


def test_monte_carlo_resampling_is_deterministic():
    trades = _trades()
    first = monte_carlo_resampling(trades, iterations=128, seed=7)
    second = monte_carlo_resampling(trades, iterations=128, seed=7)
    assert first == second
    assert first["passed"] is True
    assert first["iterations"] == 128


def test_parameter_sensitivity_prefers_best_rr():
    result = parameter_sensitivity(
        {
            "2.0": {"std_metrics": {"net_pf": 1.05}},
            "3.0": {"std_metrics": {"net_pf": 1.18}},
            "4.0": {"std_metrics": {"net_pf": 1.42}},
        }
    )
    assert result["passed"] is True
    assert result["best_rr"] == 4.0
    assert result["best_profit_factor"] == 1.42


def test_regime_analysis_groups_and_scores_by_regime():
    result = regime_analysis(_trades())
    assert result["passed"] is True
    assert {row["regime"] for row in result["regimes"]} == {"trend", "mean_revert"}
