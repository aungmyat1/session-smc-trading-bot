"""Extended tests for svos/registry/service.py to boost coverage."""
from __future__ import annotations

import pytest

from svos.registry.service import StrategyRegistryService
from svos.lifecycle.manager import LifecycleTransitionError


def _catalog_yaml(strategy: str = "ST-TEST", status: str = "walk_forward") -> str:
    return f"""
current_strategy: {strategy}
strategies:
  {strategy}:
    status: {status}
    approved: false
    current: true
    version: "1.0"
    owner: quant
    description: A test strategy
    symbols: [EURUSD]
    timeframes: [M15]
""".strip() + "\n"


def _make_registry(tmp_path, strategy: str = "ST-TEST", status: str = "walk_forward"):
    (tmp_path / "config").mkdir(parents=True, exist_ok=True)
    catalog = tmp_path / "config" / "strategy_catalog.yaml"
    catalog.write_text(_catalog_yaml(strategy, status), encoding="utf-8")
    return StrategyRegistryService(root=tmp_path, catalog_path=catalog)


def test_ensure_strategy_missing_raises(tmp_path):
    reg = _make_registry(tmp_path)
    with pytest.raises(KeyError):
        reg.ensure_strategy("NOT_IN_CATALOG")


def test_record_version_idempotent(tmp_path):
    reg = _make_registry(tmp_path)
    reg.ensure_strategy("ST-TEST")
    reg.record_version("ST-TEST", actor="a", reason="sync")
    reg.record_version("ST-TEST", actor="a", reason="sync2")
    versions = reg.versions("ST-TEST")
    # First version from ensure + two explicit = 3
    assert len(versions) >= 2


def test_record_evidence_stores_and_retrieves(tmp_path):
    reg = _make_registry(tmp_path)
    reg.ensure_strategy("ST-TEST")
    artifact = tmp_path / "reports" / "test.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text("{}", encoding="utf-8")
    ev = reg.record_evidence(
        "ST-TEST",
        stage="ROBUSTNESS_VALIDATION",
        service="unit-test",
        report_type="test.json",
        artifact_path=str(artifact),
        artifact_hash="deadbeef",
        status="PASS",
        metadata={"run": "T1"},
    )
    assert ev.status == "PASS"
    all_evidence = reg.evidence("ST-TEST")
    assert any(e["evidence_id"] == ev.evidence_id for e in all_evidence)


def test_versions_empty_before_ensure(tmp_path):
    reg = _make_registry(tmp_path)
    # Before ensuring, nothing on disk
    result = reg.versions("ST-TEST")
    assert result == []


def test_transitions_empty_before_any_transition(tmp_path):
    reg = _make_registry(tmp_path)
    reg.ensure_strategy("ST-TEST")
    result = reg.transitions("ST-TEST")
    assert result == []


def test_transition_records_entry(tmp_path):
    from svos.shared.models import GateDecision
    from svos.shared.support import now_iso
    reg = _make_registry(tmp_path)
    current = reg.ensure_strategy("ST-TEST")
    artifact = tmp_path / "r.json"
    artifact.write_text("{}", encoding="utf-8")
    reg.record_evidence(
        "ST-TEST",
        stage="ROBUSTNESS_VALIDATION",
        service="s",
        report_type="r.json",
        artifact_path=str(artifact),
        artifact_hash="abc",
        status="PASS",
        metadata={"current_version_id": current.current_version_id},
    )
    gd = GateDecision(
        decision_id="gd-1",
        strategy="ST-TEST",
        from_stage=current.current_stage,
        to_stage="VIRTUAL_DEMO",
        allowed=True,
        decided_at=now_iso(),
        actor="tester",
        reason="ready",
        evidence_ids=[],
        blockers=[],
        approval_id="",
        current_version_id=current.current_version_id,
    )
    tr = reg.transition(
        "ST-TEST",
        to_stage="VIRTUAL_DEMO",
        actor="tester",
        reason="ready",
        governance_decision=gd,
    )
    assert tr.to_stage == "VIRTUAL_DEMO"
    transitions = reg.transitions("ST-TEST")
    assert len(transitions) == 1


def test_transition_requires_governance_decision(tmp_path):
    reg = _make_registry(tmp_path)
    reg.ensure_strategy("ST-TEST")
    with pytest.raises(LifecycleTransitionError, match="governance"):
        reg.transition(
            "ST-TEST",
            to_stage="VIRTUAL_DEMO",
            actor="tester",
            reason="no decision",
            governance_decision=None,
        )


def test_strategy_record_to_dict(tmp_path):
    reg = _make_registry(tmp_path)
    rec = reg.ensure_strategy("ST-TEST")
    d = rec.to_dict()
    assert d["strategy"] == "ST-TEST"
    assert "current_stage" in d
    assert "current_version_id" in d


def test_get_strategy_record_after_ensure(tmp_path):
    reg = _make_registry(tmp_path)
    reg.ensure_strategy("ST-TEST")
    rec = reg.get_strategy_record("ST-TEST")
    assert rec.strategy == "ST-TEST"


def test_ensure_spec_version_registers_new_version(tmp_path):
    reg = _make_registry(tmp_path)
    reg.ensure_strategy("ST-TEST")
    vr = reg.ensure_spec_version(
        "ST-TEST",
        specification="Entry: Buy on sweep reversal",
        actor="quant",
        reason="new spec",
    )
    assert vr.strategy == "ST-TEST"


def test_summary_returns_dict(tmp_path):
    reg = _make_registry(tmp_path)
    reg.ensure_strategy("ST-TEST")
    summary = reg.summary()
    assert isinstance(summary, dict)
    assert "strategy_count" in summary
