from __future__ import annotations

import json
from pathlib import Path

import pytest

from svos.lifecycle import LifecycleTransitionError, StrategyLifecycleManager
from svos.governance import GovernanceGateError
from svos.orchestration import SVOSPlatform
from svos.registry import StrategyRegistryService


def _catalog_text() -> str:
    return """
current_strategy: ST-A2
strategies:
  ST-A2:
    status: walk_forward
    approved: true
    current: true
    version: "2.1"
    owner: quant
    description: Session liquidity reversal production candidate
    deployment_target: execution
    symbols: [EURUSD, GBPUSD]
    timeframes: [M15, H4]
""".strip() + "\n"


def _setup_repo(tmp_path: Path) -> Path:
    (tmp_path / "config").mkdir(parents=True, exist_ok=True)
    (tmp_path / "reports").mkdir(parents=True, exist_ok=True)
    (tmp_path / "config" / "strategy_catalog.yaml").write_text(_catalog_text(), encoding="utf-8")
    return tmp_path / "config" / "strategy_catalog.yaml"


def test_lifecycle_rejects_illegal_transition():
    manager = StrategyLifecycleManager()
    with pytest.raises(LifecycleTransitionError):
        manager.validate_transition("DRAFT", "STATISTICAL_VALIDATION")


def test_lifecycle_supports_research_failure_loop_without_execution_promotion():
    manager = StrategyLifecycleManager()
    manager.validate_transition("ROBUSTNESS_VALIDATION", "REFINEMENT")
    manager.validate_transition("REFINEMENT", "AUDIT")
    with pytest.raises(LifecycleTransitionError):
        manager.validate_transition("REFINEMENT", "VIRTUAL_DEMO")


def test_registry_bootstraps_and_preserves_append_only_history(tmp_path):
    catalog = _setup_repo(tmp_path)
    registry = StrategyRegistryService(root=tmp_path, catalog_path=catalog)

    record = registry.ensure_strategy("ST-A2")
    assert record.current_stage == "ROBUSTNESS_VALIDATION"
    assert record.version_count == 1

    registry.record_version("ST-A2", actor="tester", reason="catalog sync")
    registry.record_evidence(
        "ST-A2",
        stage="ROBUSTNESS_VALIDATION",
        service="svos",
        report_type="validation.json",
        artifact_path=str(tmp_path / "reports" / "robustness.json"),
        artifact_hash="abc123",
        status="PASS",
        metadata={"source": "test"},
    )

    versions = registry.versions("ST-A2")
    evidence = registry.evidence("ST-A2")
    assert len(versions) == 2
    assert versions[0]["version_id"] != versions[1]["version_id"]
    assert evidence[0]["metadata"]["source"] == "test"


def test_platform_records_standardized_evidence_and_audited_transition(tmp_path):
    catalog = _setup_repo(tmp_path)
    platform = SVOSPlatform(root=tmp_path, catalog_path=catalog)
    platform.bootstrap()

    artifact = tmp_path / "reports" / "audit.json"
    artifact.write_text(json.dumps({"status": "PASS"}), encoding="utf-8")

    recorded = platform.record_report_evidence(
        strategy="ST-A2",
        stage="ROBUSTNESS_VALIDATION",
        service="svos",
        report_type="audit.json",
        artifact_path=artifact,
        status="PASS",
        metadata={"runner": "unit-test"},
    )
    transition = platform.audited_transition(
        "ST-A2",
        to_stage="VIRTUAL_DEMO",
        actor="governance",
        reason="Research evidence accepted",
    )

    assert recorded["report"]["artifact_hash"]
    assert recorded["evidence"]["metadata"]["report_id"] == recorded["report"]["report_id"]
    assert transition["from_stage"] == "ROBUSTNESS_VALIDATION"
    assert transition["to_stage"] == "VIRTUAL_DEMO"
    assert transition["metadata"]["governance_decision_id"]
    assert platform.strategy_summary("ST-A2")["record"]["transition_count"] == 1


def test_governance_blocks_transition_without_current_version_pass_evidence(tmp_path):
    catalog = _setup_repo(tmp_path)
    platform = SVOSPlatform(root=tmp_path, catalog_path=catalog)
    platform.bootstrap()

    with pytest.raises(GovernanceGateError, match="No PASS evidence"):
        platform.audited_transition("ST-A2", to_stage="VIRTUAL_DEMO", reason="Qualification review")

    summary = platform.strategy_summary("ST-A2")
    assert summary["record"]["current_stage"] == "ROBUSTNESS_VALIDATION"
    assert summary["gate_decisions"][-1]["allowed"] is False


def test_direct_registry_transition_cannot_bypass_governance(tmp_path):
    catalog = _setup_repo(tmp_path)
    registry = StrategyRegistryService(root=tmp_path, catalog_path=catalog)
    registry.ensure_strategy("ST-A2")

    with pytest.raises(LifecycleTransitionError, match="governance gate decision"):
        registry.transition("ST-A2", to_stage="VIRTUAL_DEMO")


def test_evidence_from_previous_strategy_version_does_not_qualify(tmp_path):
    catalog = _setup_repo(tmp_path)
    platform = SVOSPlatform(root=tmp_path, catalog_path=catalog)
    platform.bootstrap()
    artifact = tmp_path / "reports" / "robustness.json"
    artifact.write_text('{"status":"PASS"}', encoding="utf-8")
    platform.record_report_evidence(
        strategy="ST-A2",
        stage="ROBUSTNESS_VALIDATION",
        service="svos",
        report_type="robustness.json",
        artifact_path=artifact,
        status="PASS",
    )
    platform.registry.record_version("ST-A2", actor="tester", reason="new version")

    with pytest.raises(GovernanceGateError, match="strategy version"):
        platform.audited_transition("ST-A2", to_stage="VIRTUAL_DEMO", reason="Qualification review")


def test_production_approval_transition_is_disabled_during_construction(tmp_path):
    catalog = _setup_repo(tmp_path)
    platform = SVOSPlatform(root=tmp_path, catalog_path=catalog)
    platform.bootstrap()
    state_path = tmp_path / "data" / "svos" / "registry" / "ST-A2" / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["current_stage"] = "VIRTUAL_DEMO"
    state_path.write_text(json.dumps(state), encoding="utf-8")
    with pytest.raises(LifecycleTransitionError, match="Illegal lifecycle transition"):
        platform.approve_transition(
            "ST-A2",
            to_stage="PRODUCTION_APPROVAL",
            approver="risk-committee",
            reason="Request production approval",
        )


def test_governance_requires_an_audit_reason(tmp_path):
    catalog = _setup_repo(tmp_path)
    platform = SVOSPlatform(root=tmp_path, catalog_path=catalog)
    platform.bootstrap()
    artifact = tmp_path / "reports" / "robustness.json"
    artifact.write_text('{"status":"PASS"}', encoding="utf-8")
    platform.record_report_evidence(
        strategy="ST-A2",
        stage="ROBUSTNESS_VALIDATION",
        service="svos",
        report_type="robustness.json",
        artifact_path=artifact,
        status="PASS",
    )

    with pytest.raises(GovernanceGateError, match="audit reason"):
        platform.audited_transition("ST-A2", to_stage="VIRTUAL_DEMO")
