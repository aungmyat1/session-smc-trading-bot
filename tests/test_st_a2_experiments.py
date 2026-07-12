from __future__ import annotations

from research.experiments.st_a2 import _filter_for, _ranking_score, _stress_metrics


def test_stress_metrics_applies_double_cost() -> None:
    rows = [
        {"gross_pnl": 3.0, "spread_cost": 0.2, "commission_cost": 0.1, "slippage_cost": 0.0},
        {"gross_pnl": -1.0, "spread_cost": 0.2, "commission_cost": 0.1, "slippage_cost": 0.0},
    ]

    metrics = _stress_metrics(rows, 2.0)

    assert metrics["trade_count"] == 2
    assert round(metrics["net_profit"], 6) == 0.8
    assert round(metrics["profit_factor"], 6) == round(2.4 / 1.6, 6)


def test_cost_filter_uses_predeclared_threshold() -> None:
    predicate, resolved = _filter_for({"type": "max_cost_ratio", "max_cost_to_gross_abs": 0.15})

    assert resolved == {"max_cost_to_gross_abs": 0.15}
    assert predicate({"gross_pnl": 2.0, "spread_cost": 0.1, "commission_cost": 0.1, "slippage_cost": 0.0})
    assert not predicate({"gross_pnl": 1.0, "spread_cost": 0.2, "commission_cost": 0.0, "slippage_cost": 0.0})


def test_ranking_score_rewards_pf_sharpe_dd_and_retention() -> None:
    weights = {
        "pf_2x_improvement": 0.35,
        "sharpe_improvement": 0.25,
        "drawdown_reduction": 0.20,
        "trade_count_retention": 0.10,
        "robustness": 0.10,
    }

    strong = _ranking_score({"pf_2x": 0.4, "sharpe": 0.3, "drawdown_r": 5.0}, 0.8, 0.2, weights)
    weak = _ranking_score({"pf_2x": -0.1, "sharpe": 0.0, "drawdown_r": -2.0}, 0.9, -0.1, weights)

    assert strong > weak
