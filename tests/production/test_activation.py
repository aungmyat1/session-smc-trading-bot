from __future__ import annotations

from pathlib import Path

from production.activation import ProductionActivationService
from production.importer import DeploymentImportService
from production.verifier import ProductionPreflightVerifier
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


def test_activation_service_stages_disabled_runtime_after_preflight(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("LIVE_TRADING", "false")
    monkeypatch.setenv("DEMO_ONLY", "true")
    catalog = _setup_repo(tmp_path)
    deployment = DeploymentStatusService(root=tmp_path, catalog_path=catalog).create_deployment(strategy="ST-A2", actor="risk")
    DeploymentImportService(root=tmp_path).import_deployment(deployment["deployment_id"])
    ProductionPreflightVerifier(root=tmp_path).verify_import(deployment["deployment_id"])

    record = ProductionActivationService(root=tmp_path).stage_runtime(deployment["deployment_id"], actor="risk")
    stored = ProductionActivationService(root=tmp_path).activation_status(deployment["deployment_id"])

    assert record.activation_status == "STAGED_DISABLED"
    assert record.runtime_ready is True
    assert record.activated is False
    assert stored["deployment_id"] == deployment["deployment_id"]


def test_activation_service_blocks_live_request(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("LIVE_TRADING", "false")
    monkeypatch.setenv("DEMO_ONLY", "true")
    catalog = _setup_repo(tmp_path)
    deployment = DeploymentStatusService(root=tmp_path, catalog_path=catalog).create_deployment(strategy="ST-A2", actor="risk")
    DeploymentImportService(root=tmp_path).import_deployment(deployment["deployment_id"])
    ProductionPreflightVerifier(root=tmp_path).verify_import(deployment["deployment_id"])

    record = ProductionActivationService(root=tmp_path).stage_runtime(
        deployment["deployment_id"],
        actor="risk",
        request_live=True,
    )

    assert record.activation_status == "BLOCKED"
    assert record.live_trading_enabled is False
