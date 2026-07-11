from __future__ import annotations

from pathlib import Path

import pytest

from research.optimization_runner import OptimizationExperiment, compare_metrics, promotion_decision
from research.strategy_diagnostics import classify_failures


def test_diagnostics_detect_low_win_rate_high_rr_and_few_trades() -> None:
    report = {
        "strategy": "ST-A2",
        "status": "FAIL",
        "metrics": {
            "trades": 25,
            "win_rate": 0.25,
            "average_R": 2.4,
            "profit_factor_after_cost": 1.1,
            "max_drawdown": 8.0,
        },
    }

    diagnosis = classify_failures(report)
    case_ids = {case["case_id"] for case in diagnosis["detected_failures"]}

    assert "LOW_WIN_RATE_HIGH_RR" in case_ids
    assert "TOO_FEW_TRADES" in case_ids


def test_diagnostics_detect_cost_problem() -> None:
    report = {
        "strategy": "ST-A2",
        "metrics": {
            "trades": 220,
            "win_rate": 0.45,
            "average_R": 1.2,
            "gross_profit": 100.0,
            "net_profit": -5.0,
            "gross_pnl": 100.0,
            "spread_cost": 70.0,
            "commission": 25.0,
            "slippage": 10.0,
            "net_pnl": -5.0,
        },
    }

    diagnosis = classify_failures(report)
    cost_case = next(case for case in diagnosis["detected_failures"] if case["case_id"] == "GOOD_GROSS_BAD_NET")

    assert cost_case["measurements"]["cost_percentage_of_profit"] == 1.05


def test_experiment_rejects_multi_category_changes() -> None:
    experiment = OptimizationExperiment(
        experiment_id="OPT-1",
        strategy="ST-A2",
        baseline_version="1.0",
        change_category="entry+exit",
        change="Improve confirmation and exits",
        reason="Bad idea",
        training_period="2023-07-01..2025-06-30",
        validation_period="2025-07-01..2025-12-31",
    )

    with pytest.raises(ValueError):
        experiment.to_row()


def test_promotion_decision_requires_walk_forward_pass(tmp_path: Path) -> None:
    baseline = {"strategy": "ST-A2", "version": "1.0", "metrics": {"profit_factor": 1.1, "sharpe": 1.0, "max_drawdown": 10.0}}
    candidate = {"strategy": "ST-A2", "version": "1.1", "metrics": {"profit_factor": 1.3, "sharpe": 1.2, "max_drawdown": 11.0}}

    decision = promotion_decision(baseline, candidate, {"status": "NOT_RUN"}, tmp_path / "decision.md")

    assert decision == "REJECT"


def test_compare_metrics_marks_missing_candidate_as_needs_more_data() -> None:
    report = compare_metrics({"metrics": {"profit_factor": 1.0}})

    assert report["status"] == "NEEDS_MORE_DATA"
