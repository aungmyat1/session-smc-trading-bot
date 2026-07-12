"""Tests for svos/reports/stage_package.py"""
from __future__ import annotations

from typing import Any


from svos.reports.stage_package import (
    SCHEMA_VERSION,
    PUBLIC_STAGES,
    StageReportPackage,
    _hash_payload,
    _is_missing_evidence,
    _now,
    _public_status,
    _checks,
    _safe_component,
    _virtual_demo_route,
    write_stage_report_package,
)


def _make_stage(
    stage: str,
    status: str = "PASS",
    can_promote: bool = True,
    issues: list | None = None,
    fix_instructions: list | None = None,
    metadata: dict | None = None,
) -> dict[str, Any]:
    return {
        "stage": stage,
        "status": status,
        "can_promote": can_promote,
        "issues": issues or [],
        "fix_instructions": fix_instructions or [],
        "metadata": metadata or {},
    }


# ── helpers ──────────────────────────────────────────────────────────────────

def test_now_returns_iso_string():
    result = _now()
    assert "T" in result


def test_hash_payload_deterministic():
    payload = {"key": "value", "num": 42}
    assert _hash_payload(payload) == _hash_payload(payload)
    assert _hash_payload(payload) != _hash_payload({"key": "other"})


def test_safe_component_cleans_special_chars():
    assert _safe_component("ST-A2 v1.0", "fallback") == "ST-A2-v1.0"
    assert _safe_component("", "fallback") == "fallback"
    assert _safe_component("valid-name", "fb") == "valid-name"


def test_is_missing_evidence_true_on_missing_input_code():
    stage = {"issues": [{"code": "missing_input", "severity": "ERROR"}]}
    assert _is_missing_evidence(stage)


def test_is_missing_evidence_false_when_no_issues():
    assert not _is_missing_evidence({"issues": []})


def test_is_missing_evidence_false_on_non_missing_codes():
    stage = {"issues": [{"code": "pf_too_low", "severity": "ERROR"}]}
    assert not _is_missing_evidence(stage)


# ── _public_status ────────────────────────────────────────────────────────────

def test_public_status_not_run_on_empty():
    assert _public_status([], "strategy_audit") == "NOT_RUN"


def test_public_status_pass_all_pass():
    source = [{"status": "PASS"}, {"status": "PASS"}]
    assert _public_status(source, "backtest") == "PASS"


def test_public_status_fail_on_non_pass():
    source = [{"status": "FAIL", "issues": [{"code": "bad_edge"}]}]
    assert _public_status(source, "backtest") == "FAIL"


def test_public_status_blocked_on_missing_evidence():
    source = [{"status": "FAIL", "issues": [{"code": "missing_input"}]}]
    assert _public_status(source, "backtest") == "BLOCKED"


def test_public_status_virtual_demo_not_run_without_vd_stage():
    source = [{"stage": "verification_ready", "status": "PASS"}]
    assert _public_status(source, "virtual_demo") == "NOT_RUN"


# ── _checks ────────────────────────────────────────────────────────────────────

def test_checks_builds_from_validation_metadata():
    source = [
        {
            "stage": "audit",
            "status": "PASS",
            "metadata": {
                "validation": {
                    "checks": [
                        {"name": "spec_complete", "passed": True, "severity": "ERROR", "message": "ok"}
                    ]
                }
            },
        }
    ]
    checks = _checks(source)
    assert len(checks) == 1
    assert checks[0]["name"] == "spec_complete"
    assert checks[0]["passed"]
    assert checks[0]["hard_gate"]


def test_checks_fallback_to_stage_gate():
    source = [{"stage": "backtest", "status": "PASS", "metadata": {}}]
    checks = _checks(source)
    assert len(checks) == 1
    assert checks[0]["name"] == "backtest_gate"
    assert checks[0]["passed"]


def test_checks_validation_report_results():
    source = [
        {
            "stage": "audit",
            "status": "PASS",
            "metadata": {
                "validation_report": {
                    "validator_results": [
                        {"validator_name": "AuditValidator", "score": 95, "status": "PASS"}
                    ]
                }
            },
        }
    ]
    checks = _checks(source)
    assert any(c["name"] == "AuditValidator" for c in checks)


def test_checks_raw_checks_dict():
    source = [
        {
            "stage": "robustness",
            "status": "PASS",
            "metadata": {
                "checks": {"walk_forward_passed": True, "monte_carlo_passed": False}
            },
        }
    ]
    checks = _checks(source)
    names = {c["name"] for c in checks}
    assert "walk_forward_passed" in names
    assert "monte_carlo_passed" in names


# ── _virtual_demo_route ────────────────────────────────────────────────────────

def test_virtual_demo_route_version_issue():
    source = [{"issues": [{"code": "version_mismatch"}]}]
    assert _virtual_demo_route(source) == "strategy_audit"


def test_virtual_demo_route_metric_drift():
    source = [{"issues": [{"code": "metric_drift_exceeded"}]}]
    assert _virtual_demo_route(source) == "backtest"


def test_virtual_demo_route_execution_issue():
    source = [{"issues": [{"code": "broker_execution_failure"}]}]
    assert _virtual_demo_route(source) == "robustness"


def test_virtual_demo_route_no_issues():
    assert _virtual_demo_route([]) == "research"


# ── write_stage_report_package ────────────────────────────────────────────────

def _make_audit_stage(status: str = "PASS") -> dict[str, Any]:
    return {
        "stage": "audit",
        "status": status,
        "can_promote": status == "PASS",
        "issues": [],
        "fix_instructions": [],
        "spec": {"fields": {"market": "Forex", "session": "London"}},
        "metadata": {
            "validation_report": {
                "validator_results": [
                    {"validator_name": "SpecValidator", "score": 90, "status": "PASS"}
                ],
                "overall_score": 90,
                "critical_issues": [],
                "warnings": [],
            },
            "overall_score": 90,
        },
    }


def test_write_stage_report_package_all_pass(tmp_path):
    stages = [_make_audit_stage("PASS")]
    result = write_stage_report_package(
        output_root=tmp_path,
        strategy_name="Test Strategy",
        strategy_id="test-strat",
        strategy_version="1.0.0",
        strategy_text="Entry: Buy when price sweeps high",
        stages=stages,
        promoted_stage="strategy_audit",
        validation_config={"minimum_trade_count": 50, "minimum_profit_factor": 1.0},
        input_payloads={"backtest": {"metrics": {"profit_factor": 1.5}}},
        release={"version": "1.0.0", "status": "candidate"},
        previous_version=None,
    )
    assert isinstance(result, StageReportPackage)
    assert result.strategy_id == "test-strat"
    assert result.summary_json.exists()
    assert result.summary_markdown.exists()
    assert len(result.stage_artifacts) == len(PUBLIC_STAGES)


def test_write_stage_report_package_audit_fail_blocks_downstream(tmp_path):
    stages = [_make_audit_stage("FAIL")]
    result = write_stage_report_package(
        output_root=tmp_path,
        strategy_name="Test Strat",
        strategy_id="ts",
        strategy_version="0.1.0",
        strategy_text="Buy everything",
        stages=stages,
        promoted_stage=None,
        validation_config={},
        input_payloads={},
        release={"version": "0.1.0"},
        previous_version=None,
    )
    # Downstream stages should be BLOCKED
    statuses = {a["stage"]: a["status"] for a in result.stage_artifacts}
    assert statuses["strategy_audit"] == "FAIL"
    assert statuses.get("historical_replay") == "BLOCKED"


def test_write_stage_report_package_creates_supporting_reports(tmp_path):
    result = write_stage_report_package(
        output_root=tmp_path,
        strategy_name="Test",
        strategy_id="ts",
        strategy_version="1.0.0",
        strategy_text="spec text",
        stages=[_make_audit_stage("PASS")],
        promoted_stage=None,
        validation_config={},
        input_payloads={},
        release={"version": "1.0.0"},
        previous_version="0.9.0",
    )
    assert len(result.supporting_artifacts) > 0


def test_write_stage_report_package_version_comparison(tmp_path):
    result = write_stage_report_package(
        output_root=tmp_path,
        strategy_name="T",
        strategy_id="ts",
        strategy_version="2.0.0",
        strategy_text="spec",
        stages=[_make_audit_stage()],
        promoted_stage=None,
        validation_config={},
        input_payloads={},
        release={},
        previous_version="1.0.0",
    )
    # The stage artifact should record version comparison
    first = result.stage_artifacts[0]
    assert first["version_comparison"]["changed"] is True
    assert first["version_comparison"]["previous_version"] == "1.0.0"


def test_schema_version_constant():
    assert SCHEMA_VERSION == "2.0.0"


def test_public_stages_structure():
    assert len(PUBLIC_STAGES) == 6
    for public_stage, label, stem in PUBLIC_STAGES:
        assert isinstance(public_stage, str)
        assert isinstance(label, str)
        assert isinstance(stem, str)
