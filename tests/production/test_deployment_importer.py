from __future__ import annotations

from pathlib import Path

from production.importer import DeploymentImportService
from svos.deployment.service import DeploymentStatusService


def _catalog_text() -> str:
    return """
current_strategy: ST-A2
strategies:
  ST-A2:
    status: production_approval
    svos_stage: PRODUCTION_APPROVAL
    approved: true
    approval:
      decision: APPROVED
      approved_at: "2026-01-01T00:00:00+00:00"
      expires_at: "2099-01-01T00:00:00+00:00"
      revoked: false
    adapter_id: ST-A2
    adapter_version: "2.1"
    parameters: {session: London}
    risk_policy: {policy_id: test-demo, max_risk_pct: 0.3}
    evidence: [{stage: VIRTUAL_DEMO, status: PASS, artifact_hash: fixture}]
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


def test_import_service_stages_local_deployment_package(tmp_path: Path) -> None:
    catalog = _setup_repo(tmp_path)
    deployment_service = DeploymentStatusService(root=tmp_path, catalog_path=catalog)
    deployment = deployment_service.create_deployment(strategy="ST-A2", actor="risk-operator")

    importer = DeploymentImportService(root=tmp_path)
    imported = importer.import_deployment(deployment["deployment_id"])
    status = importer.import_status(deployment["deployment_id"])

    assert imported.verified is True
    assert Path(imported.staged_archive_path).exists()
    assert status["deployment_id"] == deployment["deployment_id"]
    assert status["package_transport"] == "local"


def test_import_service_resolves_gcs_mirror_contract(tmp_path: Path, monkeypatch) -> None:
    catalog = _setup_repo(tmp_path)
    mirror_root = tmp_path / "gcs-mirror"
    monkeypatch.setenv("SVOS_PACKAGE_TRANSPORT", "gcs")
    monkeypatch.setenv("SVOS_GCS_BUCKET", "prod-strategy-artifacts")
    monkeypatch.setenv("SVOS_GCS_PREFIX", "packages")
    monkeypatch.setenv("SVOS_GCS_MIRROR_ROOT", str(mirror_root))
    deployment_service = DeploymentStatusService(root=tmp_path, catalog_path=catalog)
    deployment = deployment_service.create_deployment(strategy="ST-A2", actor="risk-operator")

    importer = DeploymentImportService(root=tmp_path)
    imported = importer.import_deployment(deployment["deployment_id"])

    assert imported.verified is True
    assert imported.package_transport == "gcs"
    assert imported.package_registry_uri.startswith("gs://prod-strategy-artifacts/packages/")
