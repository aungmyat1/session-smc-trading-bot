from __future__ import annotations

from collections import Counter
from typing import Any

OBJECTIVES = {
    "strategy_audit": "Verify that the strategy specification is complete, consistent, measurable, and implementable.",
    "historical_replay": "Verify that the interpreted rules produce correct signals during candle-by-candle replay.",
    "backtest": "Measure statistical edge, risk, and cost-aware historical performance.",
    "robustness": "Stress-test the strategy across time, parameters, regimes, and execution assumptions.",
    "virtual_demo": "Compare research expectations with broker-connected execution without production capital.",
    "production_approval": "Combine all qualification evidence into a controlled production decision.",
}


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _severity_breakdown(
    findings: list[dict[str, Any]], passed_checks: int
) -> dict[str, int]:
    counter = Counter(str(item.get("severity", "INFO")).upper() for item in findings)
    return {
        "critical": counter.get("CRITICAL", 0) + counter.get("ERROR", 0),
        "high": counter.get("HIGH", 0),
        "medium": counter.get("MEDIUM", 0)
        + counter.get("WARN", 0)
        + counter.get("WARNING", 0),
        "low": counter.get("LOW", 0) + counter.get("INFO", 0),
        "passed": passed_checks,
    }


def _audit_results(
    source: list[dict[str, Any]],
    findings: list[dict[str, Any]],
    checks: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    report: dict[str, Any] = {}
    for item in source:
        metadata = (
            item.get("metadata", {}) if isinstance(item.get("metadata"), dict) else {}
        )
        candidate = metadata.get("validation_report")
        if isinstance(candidate, dict):
            report = candidate
            break
    validators = [
        {
            "name": item.get("validator_name", "Validator"),
            "score": item.get("score"),
            "status": item.get("status"),
        }
        for item in report.get("validator_results", [])
        if isinstance(item, dict)
    ]
    breakdown = _severity_breakdown(
        findings, sum(1 for check in checks if check.get("passed"))
    )
    results = {
        "validator_scores": validators,
        "issue_breakdown": breakdown,
        "critical_issues": report.get("critical_issues", []),
        "warnings": report.get("warnings", []),
        "readiness_decision": report.get("readiness_decision"),
    }
    visualizations = [
        {
            "type": "donut",
            "title": "Audit Issue Distribution",
            "labels": ["Critical", "High", "Medium", "Low", "Passed"],
            "values": [
                breakdown[key]
                for key in ("critical", "high", "medium", "low", "passed")
            ],
        },
        {
            "type": "bar",
            "title": "Audit Module Scores",
            "labels": [item["name"] for item in validators],
            "values": [_number(item["score"]) for item in validators],
        },
    ]
    return results, visualizations


def _replay_results(
    payload: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    trades = (
        payload.get("trades", []) if isinstance(payload.get("trades"), list) else []
    )
    summary = dict(payload.get("replay_summary", {}) or {})
    total = int(summary.get("total_signals", len(trades)))
    invalid = int(
        summary.get("invalid_signals", len(payload.get("invalid_signals", []) or []))
    )
    valid = int(summary.get("valid_signals", max(total - invalid, 0)))
    accuracy = _number(
        summary.get("replay_accuracy", (valid / total * 100 if total else 0.0))
    )
    reasons = payload.get("invalid_signal_reasons", {}) or {}
    results = {
        "replay_summary": {
            "total_signals": total,
            "valid_signals": valid,
            "invalid_signals": invalid,
            "replay_accuracy_pct": round(accuracy, 2),
        },
        "invalid_signal_reasons": reasons,
        "replay_gallery": payload.get("replay_gallery", []),
        "state_transition_count": len(payload.get("state_transitions", []) or []),
    }
    visualizations = [
        {
            "type": "donut",
            "title": "Replay Result Distribution",
            "labels": ["Valid", "Invalid"],
            "values": [valid, invalid],
        },
        {
            "type": "bar",
            "title": "Invalid Signal Reasons",
            "labels": list(reasons.keys()),
            "values": [int(value) for value in reasons.values()],
        },
    ]
    return results, visualizations


def _backtest_results(
    payload: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    metrics = dict(payload.get("metrics", {}) or {})
    for key in ("trade_count", "expectancy", "max_drawdown", "profit_factor"):
        if key in payload:
            metrics[key] = payload[key]
    equity = payload.get("equity_curve", []) or []
    monthly = payload.get("monthly_returns", []) or []
    distribution = payload.get("trade_distribution", {}) or {}
    results = {
        "test_period": payload.get("test_period", {}),
        "account": payload.get("account", {}),
        "executive_metrics": metrics,
        "performance_breakdown": payload.get("performance_breakdown", {}),
        "risk_analysis": payload.get("risk_analysis", {}),
        "trade_distribution": distribution,
    }
    visualizations = [
        {"type": "line", "title": "Equity Curve", "series": equity},
        {"type": "bar", "title": "Monthly Performance", "series": monthly},
        {
            "type": "bar",
            "title": "Trade Distribution",
            "labels": list(distribution.keys()),
            "values": [distribution[key] for key in distribution],
        },
    ]
    return results, visualizations


def _robustness_results(
    payload: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    walk_forward = payload.get("walk_forward", []) or []
    parameter_sensitivity = payload.get("parameter_sensitivity", {}) or {}
    regimes = payload.get("regime_analysis", []) or []
    costs = payload.get("execution_cost_impact", []) or []
    monte_carlo = payload.get("monte_carlo", {}) or {}
    results = {
        "walk_forward": walk_forward,
        "monte_carlo": monte_carlo,
        "parameter_sensitivity": parameter_sensitivity,
        "regime_analysis": regimes,
        "execution_cost_impact": costs,
        "latest_metrics": payload.get("latest_metrics", {}),
        "previous_metrics": payload.get("previous_metrics", {}),
    }
    visualizations = [
        {
            "type": "bar",
            "title": "Walk-Forward Profit Factor",
            "labels": [
                str(item.get("period", ""))
                for item in walk_forward
                if isinstance(item, dict)
            ],
            "values": [
                _number(item.get("profit_factor"))
                for item in walk_forward
                if isinstance(item, dict)
            ],
        },
        {
            "type": "histogram",
            "title": "Monte Carlo Ending Balance",
            "series": monte_carlo.get("distribution", []),
        },
        {
            "type": "heatmap",
            "title": "Parameter Stability",
            "data": parameter_sensitivity,
        },
        {
            "type": "table",
            "title": "Regime Analysis",
            "rows": regimes,
        },
    ]
    return results, visualizations


def _virtual_demo_results(
    payload: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    expected = dict(payload.get("research_metrics", {}) or {})
    observed = dict(payload.get("live_metrics", {}) or {})
    comparison = []
    for metric in sorted(set(expected).intersection(observed)):
        baseline = _number(expected[metric])
        actual = _number(observed[metric])
        deviation = ((actual - baseline) / abs(baseline) * 100) if baseline else 0.0
        comparison.append(
            {
                "metric": metric,
                "expected": baseline,
                "observed": actual,
                "deviation_pct": round(deviation, 2),
            }
        )
    results = {
        "observation_window": {
            "days_monitored": payload.get("days_monitored"),
            "minimum_days": payload.get("min_demo_days"),
        },
        "performance_comparison": comparison,
        "execution_metrics": payload.get("execution_metrics", {}),
        "order_outcomes": payload.get("order_outcomes", {}),
        "risk_controls": payload.get("risk_controls", {}),
        "broker_comparison": payload.get("broker_comparison", {}),
        "signal_comparison": {
            "expected": payload.get("expected_signals"),
            "observed": payload.get("observed_signals"),
        },
        "trade_comparison": {
            "expected": payload.get("expected_trades"),
            "observed": payload.get("observed_trades"),
        },
    }
    visualizations = [
        {
            "type": "line",
            "title": "Virtual Demo Equity Curve",
            "series": payload.get("equity_curve", []) or [],
        },
        {
            "type": "comparison",
            "title": "Research vs Virtual Demo",
            "rows": comparison,
        },
    ]
    return results, visualizations


def _production_results(
    prior_reports: list[dict[str, Any]], payload: dict[str, Any]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    scorecard = [
        {
            "stage": report["stage_label"],
            "score": report.get("score"),
            "status": report["status"],
        }
        for report in prior_reports
    ]
    scores = [
        _number(item["score"]) for item in scorecard if item.get("score") is not None
    ]
    overall = round(sum(scores) / len(scores), 2) if scores else None
    results = {
        "qualification_summary": scorecard,
        "overall_qualification_score": overall,
        "confidence_pct": payload.get("confidence_pct", overall),
        "capital_allocation": payload.get("capital_allocation", "approval-gated"),
        "recommended_risk_pct": payload.get("recommended_risk_pct"),
        "monitoring_level": payload.get("monitoring_level", "high"),
    }
    return results, [
        {
            "type": "bar",
            "title": "Qualification Scores",
            "labels": [item["stage"] for item in scorecard],
            "values": [item["score"] for item in scorecard],
        }
    ]


def build_stage_evidence(
    *,
    public_stage: str,
    label: str,
    status: str,
    score: float | None,
    promotion_allowed: bool,
    source: list[dict[str, Any]],
    checks: list[dict[str, Any]],
    findings: list[dict[str, Any]],
    actions: list[str],
    metrics: dict[str, Any],
    thresholds: dict[str, Any],
    raw_payload: dict[str, Any],
    evidence_hashes: dict[str, str],
    prior_reports: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if public_stage == "strategy_audit":
        results, visualizations = _audit_results(source, findings, checks)
    elif public_stage == "historical_replay":
        results, visualizations = _replay_results(raw_payload)
    elif public_stage == "backtest":
        results, visualizations = _backtest_results(raw_payload)
    elif public_stage == "robustness":
        results, visualizations = _robustness_results(raw_payload)
    elif public_stage == "virtual_demo":
        results, visualizations = _virtual_demo_results(raw_payload)
    else:
        results, visualizations = _production_results(prior_reports, raw_payload)

    failed_checks = [check for check in checks if not check.get("passed")]
    decision_reason = (
        "All hard gates passed."
        if status == "PASS"
        else (
            findings[0].get("message", "Evidence is incomplete.")
            if findings
            else "Evidence is incomplete."
        )
    )
    sections = {
        "report_header": {"stage": label, "status": status, "score": score},
        "executive_summary": f"{label} finished with status {status} and diagnostic score {score if score is not None else 'n/a'}.",
        "objective": OBJECTIVES[public_stage],
        "scope": [
            "Strategy rules and stage-specific evidence",
            "Configured hard-gate thresholds",
            "Promotion readiness",
        ],
        "inputs": {
            "payload_fields": sorted(raw_payload.keys()),
            "evidence_hashes": evidence_hashes,
        },
        "evaluation_results": results,
        "evidence": {
            "hard_gate_results": checks,
            "metrics": metrics,
            "thresholds": thresholds,
        },
        "issues": findings,
        "recommendations": actions,
        "decision": {
            "status": status,
            "promotion_allowed": promotion_allowed,
            "reason": decision_reason,
            "failed_hard_gates": [
                check.get("name") for check in failed_checks if check.get("hard_gate")
            ],
        },
        "next_action": (
            actions[0]
            if actions
            else (
                "Proceed to the next SVOS stage."
                if promotion_allowed
                else "Await explicit approval or additional evidence."
            )
        ),
        "appendices": {"internal_sources": [item.get("stage") for item in source]},
    }
    return sections, [item for item in visualizations if item]
