"""End-to-end integration tests: strategy spec → intake → audit → evidence → lifecycle.

These tests exercise the complete Phase-0/Phase-1 research pipeline using an
in-memory catalog (no broker, no network, no PostgreSQL). They verify that:
- IntakeService produces a versioned artifact and PASS/FAIL status.
- AuditIntegrationService produces an audit report artifact and PASS/FAIL.
- Evidence records are registered in the JSONL registry.
- Lifecycle transitions follow the governance rules.
- Run manifests are persisted for reproducibility.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from svos.application.intake import IntakeService
from svos.application.audit import AuditIntegrationService
from svos.application.run_manifest import RunManifestBuilder
from svos.orchestration import SVOSPlatform


# ── fixtures ──────────────────────────────────────────────────────────────

_CATALOG_TEXT = """
current_strategy: null
strategies:
  LONDON-SWEEP:
    status: draft
    approved: false
    current: false
    version: "1.0"
    owner: quant
    description: London sweep reversal strategy
    deployment_target: null
    symbols: [EURUSD]
    timeframes: [M15]
""".strip() + "\n"

_GOOD_SPEC = """
Market: FX
Instrument: EURUSD
Timeframe: M15
Session: London killzone (07:00–10:00 UTC)
Direction: Long only when H1 bias is bullish
Entry Trigger: After a sweep of the prior session low by at least 2 pips,
  enter on the first M15 close that confirms CHoCH within 3 candles.
Confirmation: Require a BOS close and a three-candle FVG after displacement.
Invalidation: Cancel if CHoCH does not occur within 3 candles or price closes
  below the swept low before entry.
Stop Loss: 2 pips below the swept low.
Take Profit: 2R.
Risk: 0.3% fixed fractional risk per trade.
Maximum Daily Loss: 2R.
Maximum Drawdown: 8%.
Maximum Open Positions: 1.
News Rules: No trades within 15 minutes of high-impact EUR or USD news.
""".strip()

_EMPTY_SPEC = ""
_VAGUE_SPEC = "Buy when price goes up. Sell when price goes down."


def _setup(tmp_path: Path) -> tuple[Path, SVOSPlatform]:
    (tmp_path / "config").mkdir(parents=True, exist_ok=True)
    catalog = tmp_path / "config" / "strategy_catalog.yaml"
    catalog.write_text(_CATALOG_TEXT, encoding="utf-8")
    platform = SVOSPlatform(root=tmp_path, catalog_path=catalog)
    platform.bootstrap()
    return catalog, platform


# ── run manifest ──────────────────────────────────────────────────────────

def test_run_manifest_builder_creates_persisted_file(tmp_path):
    builder = RunManifestBuilder(tmp_path)
    manifest = builder.build(service="test", strategy="LONDON-SWEEP")
    assert manifest.manifest_id
    assert manifest.service == "test"
    assert manifest.strategy == "LONDON-SWEEP"
    assert manifest.engine_version == "svos-v1"
    manifest_file = tmp_path / "data" / "svos" / "manifests" / "LONDON-SWEEP" / f"{manifest.manifest_id}.json"
    assert manifest_file.exists()
    loaded = json.loads(manifest_file.read_text())
    assert loaded["manifest_id"] == manifest.manifest_id


def test_run_manifest_reproducible_flag(tmp_path):
    builder = RunManifestBuilder(tmp_path)
    manifest = builder.build(service="test", strategy="S")
    # git_commit and git_dirty come from the repo; is_reproducible depends on both
    assert isinstance(manifest.is_reproducible, bool)
    assert isinstance(manifest.git_dirty, bool)


# ── intake ────────────────────────────────────────────────────────────────

def test_intake_pass_with_good_spec(tmp_path):
    _, platform = _setup(tmp_path)
    svc = IntakeService(platform)
    result = svc.run("LONDON-SWEEP", _GOOD_SPEC, actor="test-runner")

    assert result.passed
    assert result.status == "PASS"
    assert result.version_id
    assert Path(result.report_artifact).exists()
    report = json.loads(Path(result.report_artifact).read_text())
    assert report["status"] == "PASS"
    assert report["stage"] == "INTAKE"
    assert report["strategy"] == "LONDON-SWEEP"
    assert report["report_type"] == "intake_report"
    assert "findings" in report


def test_intake_produces_evidence_record(tmp_path):
    _, platform = _setup(tmp_path)
    svc = IntakeService(platform)
    result = svc.run("LONDON-SWEEP", _GOOD_SPEC, actor="test-runner")

    evidence = platform.registry.evidence("LONDON-SWEEP")
    assert len(evidence) >= 1
    intake_ev = [e for e in evidence if e.get("stage") == "INTAKE"]
    assert intake_ev, "No INTAKE evidence recorded"
    assert intake_ev[-1]["status"] == "PASS"
    assert intake_ev[-1]["artifact_hash"]


def test_intake_transitions_draft_to_intake_on_pass(tmp_path):
    _, platform = _setup(tmp_path)
    svc = IntakeService(platform)
    svc.run("LONDON-SWEEP", _GOOD_SPEC, actor="test-runner")

    record = platform.registry.get_strategy_record("LONDON-SWEEP")
    assert record.current_stage == "INTAKE"


def test_intake_fail_with_empty_spec(tmp_path):
    _, platform = _setup(tmp_path)
    svc = IntakeService(platform)
    result = svc.run("LONDON-SWEEP", _EMPTY_SPEC, actor="test-runner")

    assert not result.passed
    assert result.status == "FAIL"
    assert any(f["code"] == "SPEC-001" for f in [f.to_dict() for f in result.findings])


def test_intake_report_has_markdown_companion(tmp_path):
    _, platform = _setup(tmp_path)
    svc = IntakeService(platform)
    result = svc.run("LONDON-SWEEP", _GOOD_SPEC)
    json_path = Path(result.report_artifact)
    md_path = json_path.with_suffix(".md")
    assert md_path.exists(), "Markdown companion report is missing"
    md_text = md_path.read_text(encoding="utf-8")
    assert "Intake Report" in md_text
    assert "LONDON-SWEEP" in md_text


def test_intake_run_manifest_persisted(tmp_path):
    _, platform = _setup(tmp_path)
    svc = IntakeService(platform)
    result = svc.run("LONDON-SWEEP", _GOOD_SPEC)
    manifests_dir = tmp_path / "data" / "svos" / "manifests" / "LONDON-SWEEP"
    assert manifests_dir.exists()
    files = list(manifests_dir.glob("*.json"))
    assert files, "No run manifest persisted by intake"


def test_intake_idempotent_on_unchanged_spec(tmp_path):
    _, platform = _setup(tmp_path)
    svc = IntakeService(platform)
    r1 = svc.run("LONDON-SWEEP", _GOOD_SPEC)
    r2 = svc.run("LONDON-SWEEP", _GOOD_SPEC)
    assert r1.version_id == r2.version_id, "Unchanged spec should produce the same version"


# ── audit ─────────────────────────────────────────────────────────────────

def test_audit_pass_with_good_spec(tmp_path):
    _, platform = _setup(tmp_path)
    intake = IntakeService(platform)
    intake.run("LONDON-SWEEP", _GOOD_SPEC, actor="test-intake")

    audit = AuditIntegrationService(platform)
    result = audit.run("LONDON-SWEEP", _GOOD_SPEC, actor="test-audit")

    assert result.version_id
    assert result.overall_score >= 0.0
    assert result.readiness_decision
    assert Path(result.report_artifact).exists()
    report = json.loads(Path(result.report_artifact).read_text())
    assert report["stage"] == "AUDIT"
    assert report["report_type"] == "audit_report"
    assert "validator_results" in report
    assert "schema_version" in report


def test_audit_produces_evidence_record(tmp_path):
    _, platform = _setup(tmp_path)
    intake = IntakeService(platform)
    intake.run("LONDON-SWEEP", _GOOD_SPEC, actor="test-intake")

    audit = AuditIntegrationService(platform)
    audit.run("LONDON-SWEEP", _GOOD_SPEC, actor="test-audit")

    evidence = platform.registry.evidence("LONDON-SWEEP")
    audit_ev = [e for e in evidence if e.get("stage") == "AUDIT"]
    assert audit_ev, "No AUDIT evidence recorded"
    assert audit_ev[-1]["artifact_hash"]


def test_audit_report_has_markdown_companion(tmp_path):
    _, platform = _setup(tmp_path)
    intake = IntakeService(platform)
    intake.run("LONDON-SWEEP", _GOOD_SPEC)

    audit = AuditIntegrationService(platform)
    result = audit.run("LONDON-SWEEP", _GOOD_SPEC)
    json_path = Path(result.report_artifact)
    md_path = json_path.with_suffix(".md")
    assert md_path.exists()
    md_text = md_path.read_text(encoding="utf-8")
    assert "Audit Report" in md_text
    assert "LONDON-SWEEP" in md_text


# ── end-to-end pipeline ───────────────────────────────────────────────────

def test_e2e_intake_then_audit_produces_lifecycle_history(tmp_path):
    _, platform = _setup(tmp_path)

    intake = IntakeService(platform)
    intake_result = intake.run("LONDON-SWEEP", _GOOD_SPEC, actor="ci")
    assert intake_result.passed

    audit = AuditIntegrationService(platform)
    audit_result = audit.run("LONDON-SWEEP", _GOOD_SPEC, actor="ci")
    # Score and decision come from the live audit engine — verify shape only
    assert audit_result.version_id
    assert isinstance(audit_result.overall_score, float)

    summary = platform.strategy_summary("LONDON-SWEEP")
    assert summary["record"]["version_count"] >= 1
    assert len(summary["evidence"]) >= 2
    intake_ev = [e for e in summary["evidence"] if e["stage"] == "INTAKE"]
    audit_ev = [e for e in summary["evidence"] if e["stage"] == "AUDIT"]
    assert intake_ev, "Missing INTAKE evidence"
    assert audit_ev, "Missing AUDIT evidence"


def test_e2e_full_pipeline_report_artifacts_exist(tmp_path):
    _, platform = _setup(tmp_path)
    intake = IntakeService(platform)
    audit = AuditIntegrationService(platform)
    ir = intake.run("LONDON-SWEEP", _GOOD_SPEC)
    ar = audit.run("LONDON-SWEEP", _GOOD_SPEC)
    assert Path(ir.report_artifact).exists()
    assert Path(ar.report_artifact).exists()
    assert Path(ir.report_artifact).with_suffix(".md").exists()
    assert Path(ar.report_artifact).with_suffix(".md").exists()
