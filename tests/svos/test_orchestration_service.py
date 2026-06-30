"""Tests for svos/orchestration/service.py (SVOSPlatform)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from svos.orchestration.service import SVOSPlatform


def _catalog_text() -> str:
    return """
current_strategy: ST-ORCH
strategies:
  ST-ORCH:
    status: walk_forward
    approved: false
    current: true
    version: "1.0"
    owner: quant
    description: Orchestration test strategy
    symbols: [EURUSD]
    timeframes: [M15]
""".strip() + "\n"


def _make_platform(tmp_path: Path) -> SVOSPlatform:
    (tmp_path / "config").mkdir(parents=True, exist_ok=True)
    (tmp_path / "reports").mkdir(parents=True, exist_ok=True)
    catalog = tmp_path / "config" / "strategy_catalog.yaml"
    catalog.write_text(_catalog_text(), encoding="utf-8")
    return SVOSPlatform(root=tmp_path, catalog_path=catalog)


def test_bootstrap_returns_strategy_count(tmp_path):
    platform = _make_platform(tmp_path)
    result = platform.bootstrap()
    assert result["strategy_count"] == 1
    assert len(result["strategies"]) == 1


def test_pg_active_is_false_without_db(tmp_path):
    platform = _make_platform(tmp_path)
    assert not platform._pg_active


def test_record_report_evidence_jsonl(tmp_path):
    platform = _make_platform(tmp_path)
    platform.bootstrap()
    artifact = tmp_path / "reports" / "test_artifact.json"
    artifact.write_text(json.dumps({"status": "PASS", "score": 90}), encoding="utf-8")

    result = platform.record_report_evidence(
        strategy="ST-ORCH",
        stage="ROBUSTNESS_VALIDATION",
        service="test-runner",
        report_type="robustness.json",
        artifact_path=artifact,
        status="PASS",
        metadata={"run_id": "test-001"},
    )
    assert "report" in result
    assert "evidence" in result
    assert result["report"]["status"] == "PASS"


def test_audited_transition_blocked_without_evidence(tmp_path):
    from svos.governance.service import GovernanceGateError
    platform = _make_platform(tmp_path)
    platform.bootstrap()
    with pytest.raises(GovernanceGateError):
        platform.audited_transition(
            "ST-ORCH",
            to_stage="VIRTUAL_DEMO",
            actor="tester",
            reason="no evidence",
        )


def test_audited_transition_succeeds_with_evidence(tmp_path):
    platform = _make_platform(tmp_path)
    current = platform.registry.ensure_strategy("ST-ORCH")
    artifact = tmp_path / "reports" / "r.json"
    artifact.write_text("{}", encoding="utf-8")
    platform.record_report_evidence(
        strategy="ST-ORCH",
        stage="ROBUSTNESS_VALIDATION",
        service="s",
        report_type="r.json",
        artifact_path=artifact,
        status="PASS",
        metadata={"current_version_id": current.current_version_id},
    )
    result = platform.audited_transition(
        "ST-ORCH",
        to_stage="VIRTUAL_DEMO",
        actor="tester",
        reason="all clear",
    )
    assert result["to_stage"] == "VIRTUAL_DEMO"


def test_approve_transition(tmp_path):
    platform = _make_platform(tmp_path)
    platform.bootstrap()
    result = platform.approve_transition(
        "ST-ORCH",
        to_stage="VIRTUAL_DEMO",
        approver="quant-lead",
        reason="peer reviewed",
    )
    assert result["to_stage"] == "VIRTUAL_DEMO"
    assert result["approver"] == "quant-lead"


def test_strategy_summary_structure(tmp_path):
    platform = _make_platform(tmp_path)
    platform.bootstrap()
    summary = platform.strategy_summary("ST-ORCH")
    assert "record" in summary
    assert "versions" in summary
    assert "evidence" in summary
    assert "gate_decisions" in summary
    assert "approvals" in summary
    assert "transitions" in summary
