from __future__ import annotations

import tarfile
from pathlib import Path

from production.importer import DeploymentImportService
from production.verifier import ProductionPreflightVerifier
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


def test_preflight_verifier_accepts_staged_disabled_package(tmp_path: Path) -> None:
    catalog = _setup_repo(tmp_path)
    deployment_service = DeploymentStatusService(root=tmp_path, catalog_path=catalog)
    deployment = deployment_service.create_deployment(strategy="ST-A2", actor="risk-operator")
    imported = DeploymentImportService(root=tmp_path).import_deployment(deployment["deployment_id"])

    result = ProductionPreflightVerifier(root=tmp_path).verify_import(deployment["deployment_id"])
    stored = ProductionPreflightVerifier(root=tmp_path).verification_status(deployment["deployment_id"])

    assert imported.verified is True
    assert result.verified is True
    assert result.verdict == "READY_DISABLED"
    assert stored["deployment_id"] == deployment["deployment_id"]
    assert Path(result.json_report_path).exists()
    assert Path(result.markdown_report_path).exists()
    assert result.json_report_id.startswith("reports__production_preflight__")
    assert result.markdown_report_id.startswith("reports__production_preflight__")
    assert any(check["name"] == "manifest_live_disabled" and check["passed"] for check in result.checks)


def test_preflight_verifier_blocks_package_missing_required_files(tmp_path: Path) -> None:
    catalog = _setup_repo(tmp_path)
    deployment_service = DeploymentStatusService(root=tmp_path, catalog_path=catalog)
    deployment = deployment_service.create_deployment(strategy="ST-A2", actor="risk-operator")
    imported = DeploymentImportService(root=tmp_path).import_deployment(deployment["deployment_id"])
    archive_path = Path(imported.staged_archive_path)

    broken_path = archive_path.with_name("broken_strategy_package.tar.gz")
    with tarfile.open(broken_path, "w:gz") as archive:
        pass
    archive_path.unlink()
    broken_path.rename(archive_path)

    result = ProductionPreflightVerifier(root=tmp_path).verify_import(deployment["deployment_id"])

    assert result.verified is False
    assert result.verdict == "BLOCKED"
    assert any(check["name"] == "required_files_present" and not check["passed"] for check in result.checks)
