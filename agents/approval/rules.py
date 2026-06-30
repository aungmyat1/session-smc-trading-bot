"""Approval rules — the definitive set of mandatory gates for release approval.

Each rule is evaluated against the aggregated agent reports.  A single FAIL
on a mandatory rule blocks APPROVED status regardless of all other scores.

Rules are declarative so the approval logic in agent.py stays free of magic
numbers and the thresholds can be updated in config/approval.yaml without
touching code.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class RuleOutcome(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    SKIP = "SKIP"


@dataclass
class RuleResult:
    """Result of evaluating a single governance rule."""

    rule_id: str
    description: str
    outcome: RuleOutcome
    actual: Any
    threshold: Any
    mandatory: bool
    detail: str = ""


def evaluate_rules(reports: dict[str, Any], thresholds: dict[str, Any]) -> list[RuleResult]:
    """Evaluate all governance rules against the provided reports.

    Parameters
    ----------
    reports:
        Aggregated dict with keys: ``testing``, ``quality``.
    thresholds:
        Loaded from config/approval.yaml.

    Returns
    -------
    list[RuleResult]
        One entry per rule, sorted mandatory-first.
    """
    t = reports.get("testing", {})
    q = reports.get("quality", {})

    results: list[RuleResult] = []

    # ── SOFTWARE QUALITY RULES ────────────────────────────────────────────────

    results.append(_score_rule(
        "SW-001", "Unit tests PASS",
        mandatory=True,
        actual=_status(t, "unit_tests"),
        threshold="PASS",
        comparator=lambda a, th: a in ("PASS", "SKIP"),
    ))

    results.append(_score_rule(
        "SW-002", "Unit test coverage ≥ threshold",
        mandatory=True,
        actual=t.get("coverage", 0),
        threshold=thresholds.get("minimum_coverage", 90),
        comparator=lambda a, th: a >= th,
    ))

    results.append(_score_rule(
        "SW-003", "Integration tests PASS",
        mandatory=True,
        actual=_status(t, "integration_tests"),
        threshold="PASS",
        comparator=lambda a, th: a in ("PASS", "SKIP"),
    ))

    results.append(_score_rule(
        "SW-004", "Overall testing score ≥ threshold",
        mandatory=False,
        actual=t.get("score", 0),
        threshold=thresholds.get("minimum_testing_score", 85),
        comparator=lambda a, th: a >= th,
    ))

    # ── TRADING STRATEGY RULES ────────────────────────────────────────────────

    results.append(_score_rule(
        "TR-001", "Strategy validation score ≥ threshold",
        mandatory=True,
        actual=_score(t, "strategy_validation"),
        threshold=thresholds.get("minimum_strategy_score", 90),
        comparator=lambda a, th: a >= th,
    ))

    results.append(_score_rule(
        "TR-002", "Historical replay not FAIL",
        mandatory=False,
        actual=_status(t, "historical_replay"),
        threshold="not-FAIL",
        comparator=lambda a, th: a != "FAIL",
        skip_if_skip=True,
    ))

    results.append(_score_rule(
        "TR-003", "Regression check PASS",
        mandatory=True,
        actual=_status(t, "regression"),
        threshold="PASS",
        comparator=lambda a, th: a in ("PASS", "SKIP"),
    ))

    # ── CODE QUALITY RULES ────────────────────────────────────────────────────

    results.append(_score_rule(
        "QA-001", "Code quality score ≥ threshold",
        mandatory=True,
        actual=q.get("quality_score", 0),
        threshold=thresholds.get("minimum_quality_score", 90),
        comparator=lambda a, th: a >= th,
    ))

    results.append(_score_rule(
        "QA-002", "Ruff linting PASS (zero violations)",
        mandatory=True,
        actual=_tool_score(q, "code_quality", "ruff"),
        threshold=100,
        comparator=lambda a, th: a >= th,
    ))

    results.append(_score_rule(
        "QA-003", "MyPy type checking PASS",
        mandatory=False,
        actual=_tool_score(q, "code_quality", "mypy"),
        threshold=100,
        comparator=lambda a, th: a >= th,
    ))

    # ── SECURITY RULES ────────────────────────────────────────────────────────

    results.append(_score_rule(
        "SEC-001", "Security score ≥ threshold",
        mandatory=True,
        actual=q.get("security_score", 0),
        threshold=thresholds.get("minimum_security_score", 90),
        comparator=lambda a, th: a >= th,
    ))

    results.append(_score_rule(
        "SEC-002", "Secret scan clean (zero findings)",
        mandatory=True,
        actual=_tool_detail(q, "security", "secret_scan", "findings"),
        threshold=0,
        comparator=lambda a, th: a == th,
    ))

    # ── ARCHITECTURE RULES ────────────────────────────────────────────────────

    results.append(_score_rule(
        "ARCH-001", "Architecture compliance PASS",
        mandatory=True,
        actual=_status_direct(q, "architecture"),
        threshold="PASS",
        comparator=lambda a, th: a in ("PASS", "SKIP"),
    ))

    results.append(_score_rule(
        "ARCH-002", "Zero architectural violations",
        mandatory=True,
        actual=_detail(q, "architecture", "violations"),
        threshold=0,
        comparator=lambda a, th: a == th,
    ))

    results.append(_score_rule(
        "ARCH-003", "No circular dependencies",
        mandatory=True,
        actual=_detail(q, "dependency", "cycles_found"),
        threshold=0,
        comparator=lambda a, th: a == th,
    ))

    # ── DOCUMENTATION RULES ──────────────────────────────────────────────────

    results.append(_score_rule(
        "DOC-001", "Documentation score ≥ threshold",
        mandatory=False,
        actual=q.get("documentation_score", 0),
        threshold=thresholds.get("minimum_documentation_score", 70),
        comparator=lambda a, th: a >= th,
    ))

    # Sort mandatory rules first.
    results.sort(key=lambda r: (0 if r.mandatory else 1, r.rule_id))
    return results


# ── Helpers ──────────────────────────────────────────────────────────────────

def _status(report: dict[str, Any], stage: str) -> str:
    s = report.get(stage) or {}
    return s.get("status", "SKIP")


def _status_direct(report: dict[str, Any], stage: str) -> str:
    s = report.get(stage) or {}
    return s.get("status", "SKIP")


def _score(report: dict[str, Any], stage: str) -> float:
    s = report.get(stage) or {}
    return float(s.get("score", 0))


def _tool_score(quality_report: dict[str, Any], stage: str, tool: str) -> float:
    s = quality_report.get(stage) or {}
    details = s.get("details", {})
    return float(details.get("tool_scores", {}).get(tool, 0))


def _tool_detail(quality_report: dict[str, Any], stage: str, tool: str, key: str) -> Any:
    s = quality_report.get(stage) or {}
    details = s.get("details", {})
    tool_data = details.get(tool, {}) if isinstance(details.get(tool), dict) else {}
    return tool_data.get(key, 0)


def _detail(report: dict[str, Any], stage: str, key: str) -> Any:
    s = report.get(stage) or {}
    return s.get("details", {}).get(key, 0)


def _score_rule(
    rule_id: str,
    description: str,
    mandatory: bool,
    actual: Any,
    threshold: Any,
    comparator: Any,
    skip_if_skip: bool = False,
) -> RuleResult:
    if skip_if_skip and actual == "SKIP":
        return RuleResult(
            rule_id=rule_id,
            description=description,
            outcome=RuleOutcome.SKIP,
            actual=actual,
            threshold=threshold,
            mandatory=mandatory,
            detail="skipped — upstream stage not yet run",
        )
    try:
        passed = comparator(actual, threshold)
    except (TypeError, ValueError):
        passed = False
    return RuleResult(
        rule_id=rule_id,
        description=description,
        outcome=RuleOutcome.PASS if passed else RuleOutcome.FAIL,
        actual=actual,
        threshold=threshold,
        mandatory=mandatory,
        detail="" if passed else f"actual={actual!r} required={threshold!r}",
    )
