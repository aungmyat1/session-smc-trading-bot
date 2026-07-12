"""Tests for svos/reports/evidence_package.py"""
from __future__ import annotations


import pytest

from svos.reports.evidence_package import (
    OBJECTIVES,
    _audit_results,
    _backtest_results,
    _number,
    _production_results,
    _replay_results,
    _robustness_results,
    _severity_breakdown,
    _virtual_demo_results,
    build_stage_evidence,
)


def test_number_converts_valid():
    assert _number("3.14") == pytest.approx(3.14)
    assert _number(42) == 42.0


def test_number_returns_default_on_invalid():
    assert _number(None) == 0.0
    assert _number("bad") == 0.0
    assert _number("bad", default=99.0) == 99.0


def test_severity_breakdown_counts():
    findings = [
        {"severity": "CRITICAL"},
        {"severity": "HIGH"},
        {"severity": "WARN"},
        {"severity": "LOW"},
        {"severity": "INFO"},
        {"severity": "ERROR"},
    ]
    result = _severity_breakdown(findings, passed_checks=5)
    assert result["critical"] == 2  # CRITICAL + ERROR
    assert result["high"] == 1
    assert result["medium"] == 1  # WARN
    assert result["low"] == 2  # LOW + INFO
    assert result["passed"] == 5


def test_audit_results_empty_source():
    results, viz = _audit_results([], [], [])
    assert isinstance(results, dict)
    assert isinstance(viz, list)


def test_audit_results_with_validation_report():
    source = [
        {
            "stage": "audit",
            "metadata": {
                "validation_report": {
                    "validator_results": [
                        {"validator_name": "SpecValidator", "score": 90, "status": "PASS"}
                    ],
                    "critical_issues": [],
                    "warnings": [],
                    "readiness_decision": "PASS",
                }
            },
        }
    ]
    results, viz = _audit_results(source, [], [{"passed": True}])
    assert results["validator_scores"][0]["name"] == "SpecValidator"
    assert len(viz) == 2


def test_replay_results_basic():
    payload = {
        "replay_summary": {
            "total_signals": 100,
            "valid_signals": 90,
            "invalid_signals": 10,
        },
        "invalid_signal_reasons": {"lookahead": 5, "missing_data": 5},
    }
    results, viz = _replay_results(payload)
    assert results["replay_summary"]["total_signals"] == 100
    assert results["replay_summary"]["replay_accuracy_pct"] == 90.0
    assert len(viz) == 2


def test_replay_results_empty_payload():
    results, viz = _replay_results({})
    assert results["replay_summary"]["total_signals"] == 0


def test_backtest_results_basic():
    payload = {
        "metrics": {"profit_factor": 1.5, "trade_count": 100},
        "equity_curve": [1000, 1100, 1200],
        "monthly_returns": [{"month": "2024-01", "return": 10}],
        "trade_distribution": {"win": 60, "loss": 40},
    }
    results, viz = _backtest_results(payload)
    assert results["executive_metrics"]["profit_factor"] == 1.5
    assert len(viz) == 3


def test_robustness_results_basic():
    payload = {
        "walk_forward": [{"period": "2023", "profit_factor": 1.4}],
        "monte_carlo": {"distribution": [1000, 1100, 1200], "p10": 900},
        "parameter_sensitivity": {"sl_pips": {"min": 5, "max": 20}},
        "regime_analysis": [{"regime": "bull", "pf": 1.6}],
        "execution_cost_impact": [{"cost": 0.5, "pf": 1.3}],
    }
    results, viz = _robustness_results(payload)
    assert results["walk_forward"][0]["period"] == "2023"
    assert len(viz) == 4


def test_virtual_demo_results_comparison():
    payload = {
        "research_metrics": {"profit_factor": 1.5, "win_rate": 0.6},
        "live_metrics": {"profit_factor": 1.45, "win_rate": 0.58},
        "days_monitored": 30,
        "min_demo_days": 20,
    }
    results, viz = _virtual_demo_results(payload)
    comparison = results["performance_comparison"]
    assert any(item["metric"] == "profit_factor" for item in comparison)
    assert len(viz) == 2


def test_production_results_scorecard():
    prior_reports = [
        {"stage_label": "Audit", "status": "PASS", "score": 90},
        {"stage_label": "Backtest", "status": "PASS", "score": 80},
    ]
    results, viz = _production_results(prior_reports, {})
    assert results["overall_qualification_score"] == 85.0
    assert len(results["qualification_summary"]) == 2
    assert len(viz) == 1


def test_build_stage_evidence_strategy_audit():
    source = [
        {
            "stage": "audit",
            "status": "PASS",
            "metadata": {
                "validation_report": {
                    "validator_results": [],
                    "critical_issues": [],
                    "warnings": [],
                }
            },
        }
    ]
    sections, viz = build_stage_evidence(
        public_stage="strategy_audit",
        label="Strategy Audit",
        status="PASS",
        score=90.0,
        promotion_allowed=True,
        source=source,
        checks=[{"name": "spec_check", "passed": True, "hard_gate": True}],
        findings=[],
        actions=["Proceed to next stage"],
        metrics={"trade_count": 100},
        thresholds={"min_pf": 1.0},
        raw_payload={},
        evidence_hashes={"audit": "abc123"},
        prior_reports=[],
    )
    assert sections["decision"]["status"] == "PASS"
    assert sections["decision"]["promotion_allowed"] is True
    assert "report_header" in sections


def test_build_stage_evidence_historical_replay():
    sections, _ = build_stage_evidence(
        public_stage="historical_replay",
        label="Historical Replay",
        status="PASS",
        score=85.0,
        promotion_allowed=True,
        source=[{"stage": "replay", "status": "PASS", "metadata": {}}],
        checks=[],
        findings=[],
        actions=[],
        metrics={},
        thresholds={},
        raw_payload={"replay_summary": {"total_signals": 50, "valid_signals": 48, "invalid_signals": 2}},
        evidence_hashes={},
        prior_reports=[],
    )
    assert sections["decision"]["status"] == "PASS"


def test_build_stage_evidence_backtest():
    sections, _ = build_stage_evidence(
        public_stage="backtest",
        label="Backtest",
        status="FAIL",
        score=40.0,
        promotion_allowed=False,
        source=[{"stage": "backtest", "status": "FAIL", "metadata": {}}],
        checks=[{"name": "pf_gate", "passed": False, "hard_gate": True}],
        findings=[{"message": "PF below threshold", "severity": "CRITICAL"}],
        actions=["Improve entry filters"],
        metrics={"profit_factor": 0.8},
        thresholds={"min_pf": 1.0},
        raw_payload={"metrics": {"profit_factor": 0.8}},
        evidence_hashes={},
        prior_reports=[],
    )
    assert sections["decision"]["status"] == "FAIL"
    assert not sections["decision"]["promotion_allowed"]
    assert len(sections["decision"]["failed_hard_gates"]) == 1


def test_build_stage_evidence_robustness():
    sections, _ = build_stage_evidence(
        public_stage="robustness",
        label="Robustness",
        status="PASS",
        score=88.0,
        promotion_allowed=True,
        source=[{"stage": "robustness", "status": "PASS", "metadata": {}}],
        checks=[],
        findings=[],
        actions=[],
        metrics={},
        thresholds={},
        raw_payload={"walk_forward": [], "monte_carlo": {}},
        evidence_hashes={},
        prior_reports=[],
    )
    assert sections["decision"]["status"] == "PASS"


def test_build_stage_evidence_virtual_demo():
    sections, _ = build_stage_evidence(
        public_stage="virtual_demo",
        label="Virtual Demo",
        status="PASS",
        score=92.0,
        promotion_allowed=True,
        source=[{"stage": "virtual_demo", "status": "PASS", "metadata": {}}],
        checks=[],
        findings=[],
        actions=[],
        metrics={},
        thresholds={},
        raw_payload={"research_metrics": {}, "live_metrics": {}},
        evidence_hashes={},
        prior_reports=[],
    )
    assert sections["decision"]["status"] == "PASS"


def test_build_stage_evidence_production_approval():
    prior = [{"stage_label": "Audit", "status": "PASS", "score": 90}]
    sections, _ = build_stage_evidence(
        public_stage="production_approval",
        label="Production Approval",
        status="PASS",
        score=90.0,
        promotion_allowed=True,
        source=[],
        checks=[],
        findings=[],
        actions=[],
        metrics={},
        thresholds={},
        raw_payload={},
        evidence_hashes={},
        prior_reports=prior,
    )
    assert "qualification_summary" in sections["evaluation_results"]


def test_objectives_keys():
    expected = {
        "strategy_audit", "historical_replay", "backtest",
        "robustness", "virtual_demo", "production_approval"
    }
    assert set(OBJECTIVES.keys()) == expected
