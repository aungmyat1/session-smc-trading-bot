"""Tests for svos/governance/service.py"""
from __future__ import annotations

import pytest

from svos.governance.service import GovernanceGateError, GovernanceService
from svos.lifecycle.manager import StrategyLifecycleManager
from svos.registry.service import StrategyRegistryService


def _catalog_text(stage: str = "walk_forward") -> str:
    return f"""
current_strategy: TEST-STRAT
strategies:
  TEST-STRAT:
    status: {stage}
    approved: false
    current: true
    version: "1.0"
    owner: quant
    description: Test strategy
    symbols: [EURUSD]
    timeframes: [M15]
""".strip() + "\n"


def _setup(tmp_path, stage: str = "walk_forward"):
    (tmp_path / "config").mkdir(parents=True, exist_ok=True)
    (tmp_path / "reports").mkdir(parents=True, exist_ok=True)
    catalog = tmp_path / "config" / "strategy_catalog.yaml"
    catalog.write_text(_catalog_text(stage), encoding="utf-8")
    lifecycle = StrategyLifecycleManager()
    registry = StrategyRegistryService(
        root=tmp_path, catalog_path=catalog, lifecycle=lifecycle
    )
    gov = GovernanceService(root=tmp_path, registry=registry, lifecycle=lifecycle)
    return catalog, registry, gov


def test_record_approval_valid(tmp_path):
    catalog, registry, gov = _setup(tmp_path)
    registry.ensure_strategy("TEST-STRAT")
    approval = gov.record_approval(
        "TEST-STRAT",
        to_stage="VIRTUAL_DEMO",
        approver="quant-lead",
        reason="All gates passed",
    )
    assert approval.to_stage == "VIRTUAL_DEMO"
    assert approval.approver == "quant-lead"


def test_record_approval_requires_approver(tmp_path):
    _, registry, gov = _setup(tmp_path)
    registry.ensure_strategy("TEST-STRAT")
    with pytest.raises(ValueError, match="approver"):
        gov.record_approval(
            "TEST-STRAT",
            to_stage="VIRTUAL_DEMO",
            approver="",
            reason="valid reason",
        )


def test_record_approval_requires_reason(tmp_path):
    _, registry, gov = _setup(tmp_path)
    registry.ensure_strategy("TEST-STRAT")
    with pytest.raises(ValueError):
        gov.record_approval(
            "TEST-STRAT",
            to_stage="VIRTUAL_DEMO",
            approver="quant",
            reason="",
        )


def test_evaluate_transition_blocked_without_evidence(tmp_path):
    _, registry, gov = _setup(tmp_path)
    registry.ensure_strategy("TEST-STRAT")
    decision = gov.evaluate_transition(
        "TEST-STRAT",
        to_stage="VIRTUAL_DEMO",
        actor="tester",
        reason="test",
    )
    assert not decision.allowed
    assert any("PASS evidence" in b for b in decision.blockers)


def test_evaluate_transition_blocked_without_actor(tmp_path):
    _, registry, gov = _setup(tmp_path)
    registry.ensure_strategy("TEST-STRAT")
    decision = gov.evaluate_transition(
        "TEST-STRAT",
        to_stage="VIRTUAL_DEMO",
        actor="",
        reason="test",
    )
    assert not decision.allowed
    assert any("actor" in b.lower() for b in decision.blockers)


def test_evaluate_transition_blocked_without_reason(tmp_path):
    _, registry, gov = _setup(tmp_path)
    registry.ensure_strategy("TEST-STRAT")
    decision = gov.evaluate_transition(
        "TEST-STRAT",
        to_stage="VIRTUAL_DEMO",
        actor="tester",
        reason="",
    )
    assert not decision.allowed
    assert any("reason" in b.lower() for b in decision.blockers)


def test_evaluate_transition_no_evidence_required_for_draft_targets(tmp_path):
    # Transitions to REFINEMENT don't require evidence
    _, registry, gov = _setup(tmp_path)
    registry.ensure_strategy("TEST-STRAT")
    decision = gov.evaluate_transition(
        "TEST-STRAT",
        to_stage="REFINEMENT",
        actor="tester",
        reason="spec change",
    )
    # blocked only if actor/reason missing — not for evidence
    assert not any("PASS evidence" in b for b in decision.blockers)


def test_transition_raises_gate_error_without_evidence(tmp_path):
    _, registry, gov = _setup(tmp_path)
    registry.ensure_strategy("TEST-STRAT")
    with pytest.raises(GovernanceGateError):
        gov.transition(
            "TEST-STRAT",
            to_stage="VIRTUAL_DEMO",
            actor="tester",
            reason="skip",
        )


def test_transition_succeeds_with_pass_evidence(tmp_path):
    _, registry, gov = _setup(tmp_path)
    current = registry.ensure_strategy("TEST-STRAT")
    # Record PASS evidence for current stage
    artifact = tmp_path / "reports" / "robustness.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text("{}", encoding="utf-8")
    registry.record_evidence(
        "TEST-STRAT",
        stage="ROBUSTNESS_VALIDATION",
        service="test",
        report_type="robustness.json",
        artifact_path=str(artifact),
        artifact_hash="abc123",
        status="PASS",
        metadata={"current_version_id": current.current_version_id},
    )
    transition = gov.transition(
        "TEST-STRAT",
        to_stage="VIRTUAL_DEMO",
        actor="tester",
        reason="evidence is present",
    )
    assert transition.to_stage == "VIRTUAL_DEMO"


def test_decisions_empty_initially(tmp_path):
    _, registry, gov = _setup(tmp_path)
    registry.ensure_strategy("TEST-STRAT")
    assert gov.decisions("TEST-STRAT") == []


def test_approvals_empty_initially(tmp_path):
    _, registry, gov = _setup(tmp_path)
    registry.ensure_strategy("TEST-STRAT")
    assert gov.approvals("TEST-STRAT") == []


def test_decisions_recorded_after_evaluate(tmp_path):
    _, registry, gov = _setup(tmp_path)
    registry.ensure_strategy("TEST-STRAT")
    gov.evaluate_transition(
        "TEST-STRAT", to_stage="VIRTUAL_DEMO", actor="test", reason="r"
    )
    decisions = gov.decisions("TEST-STRAT")
    assert len(decisions) == 1
    assert decisions[0]["from_stage"] is not None


def test_same_stage_alias_handling(tmp_path):
    _, registry, gov = _setup(tmp_path)
    # Internal test of _same_stage via aliases used in evaluate_transition
    from svos.lifecycle.manager import StrategyStage
    assert gov._same_stage("STRATEGY_AUDIT", StrategyStage.AUDIT)
    assert gov._same_stage("BACKTEST", StrategyStage.STATISTICAL_VALIDATION)
    assert not gov._same_stage("UNKNOWN", StrategyStage.AUDIT)
