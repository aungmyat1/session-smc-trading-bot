from __future__ import annotations

from pathlib import Path

from production import DeploymentImportService, ProductionActivationService, ProductionPreflightVerifier, ProductionSummaryService
from svos.deployment.service import DeploymentStatusService


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
    strategy_spec_path: docs/specs/st_a2.md
    symbols: [EURUSD, GBPUSD]
    timeframes: [M15, H4]
""".strip() + "\n"


def _setup_repo(tmp_path: Path) -> Path:
    (tmp_path / "config").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "specs").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "specs" / "st_a2.md").write_text("# ST-A2\n", encoding="utf-8")
    (tmp_path / "requirements.txt").write_text("flask==3.0.0\n", encoding="utf-8")
    catalog = tmp_path / "config" / "strategy_catalog.yaml"
    catalog.write_text(_catalog_text(), encoding="utf-8")
    return catalog


def test_summary_service_tracks_progression_to_staged_disabled(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("LIVE_TRADING", "false")
    monkeypatch.setenv("DEMO_ONLY", "true")
    catalog = _setup_repo(tmp_path)
    deployment = DeploymentStatusService(root=tmp_path, catalog_path=catalog).create_deployment(strategy="ST-A2", actor="risk")
    summary = ProductionSummaryService(root=tmp_path)

    first = summary.summarize(deployment["deployment_id"])
    assert first.overall_status == "DEPLOYMENT_CREATED"

    DeploymentImportService(root=tmp_path).import_deployment(deployment["deployment_id"])
    second = summary.summarize(deployment["deployment_id"])
    assert second.overall_status == "IMPORTED"

    ProductionPreflightVerifier(root=tmp_path).verify_import(deployment["deployment_id"])
    third = summary.summarize(deployment["deployment_id"])
    assert third.overall_status == "READY_DISABLED"

    ProductionActivationService(root=tmp_path).stage_runtime(deployment["deployment_id"], actor="risk")
    fourth = summary.summarize(deployment["deployment_id"])
    assert fourth.overall_status == "STAGED_DISABLED"
