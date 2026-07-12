from __future__ import annotations

import json
import tarfile
from pathlib import Path

import pytest

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
    (tmp_path / "reports").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "specs" / "st_a2.md").write_text(
        "# ST-A2\n\nEntry: sweep then displacement.\n",
        encoding="utf-8",
    )
    (tmp_path / "requirements.txt").write_text("flask==3.0.0\n", encoding="utf-8")
    catalog = tmp_path / "config" / "strategy_catalog.yaml"
    catalog.write_text(_catalog_text(), encoding="utf-8")
    return catalog


def test_build_strategy_package_creates_immutable_archive_and_manifest(tmp_path: Path) -> None:
    catalog = _setup_repo(tmp_path)
    service = DeploymentStatusService(root=tmp_path, catalog_path=catalog)

    package = service.build_strategy_package("ST-A2", actor="unit-test")

    assert package["strategy"] == "ST-A2"
    assert package["version"] == "2.1"
    assert package["archive_sha256"]
    assert Path(package["content_addressed_path"]).exists()
    manifest = json.loads(Path(package["manifest_path"]).read_text(encoding="utf-8"))
    assert manifest["package_format"] == "strategy-package/v2"
    assert manifest["live_trading_enabled"] is False

    with tarfile.open(Path(package["archive_path"]), "r:gz") as archive:
        names = sorted(archive.getnames())
    assert "manifest.json" in names
    assert "approval.json" in names
    assert "strategy_spec.md" in names
    assert "evidence_manifest.json" in names
    assert "governance_snapshot.json" in names

    with tarfile.open(Path(package["archive_path"]), "r:gz") as archive:
        snapshot_payload = json.loads(archive.extractfile("governance_snapshot.json").read().decode("utf-8"))
    assert "ST-A2" in snapshot_payload.get("strategies", {})
    assert manifest["runtime_api_version"] == "system2-runtime/v2"


def test_build_strategy_package_requires_system1_private_key(tmp_path: Path, monkeypatch) -> None:
    catalog = _setup_repo(tmp_path)
    monkeypatch.delenv("SVOS_PACKAGE_SIGNING_PRIVATE_KEY", raising=False)

    service = DeploymentStatusService(root=tmp_path, catalog_path=catalog)

    with pytest.raises(ValueError, match="signing key"):
        service.build_strategy_package("ST-A2", actor="unit-test")


def test_build_strategy_package_requires_governance_approval_stage(tmp_path: Path) -> None:
    catalog = _setup_repo(tmp_path)
    catalog.write_text(
        _catalog_text().replace("status: production_approval", "status: walk_forward").replace(
            "svos_stage: PRODUCTION_APPROVAL", "svos_stage: ROBUSTNESS_VALIDATION"
        ),
        encoding="utf-8",
    )

    service = DeploymentStatusService(root=tmp_path, catalog_path=catalog)

    with pytest.raises(PermissionError, match="PRODUCTION_APPROVAL"):
        service.build_strategy_package("ST-A2", actor="unit-test")


def test_create_deployment_and_record_report_round_trip(tmp_path: Path) -> None:
    catalog = _setup_repo(tmp_path)
    service = DeploymentStatusService(root=tmp_path, catalog_path=catalog)
    report_path = tmp_path / "reports" / "deployment_check.json"
    report_path.write_text('{"health":"ok"}', encoding="utf-8")

    deployment = service.create_deployment(strategy="ST-A2", actor="risk-operator", notes="prepare prod disabled")
    report = service.record_deployment_report(
        deployment["deployment_id"],
        status="VALIDATED",
        actor="research-operator",
        summary="Dry-run validation completed",
        artifact_path=str(report_path),
    )
    status = service.deployment_status(deployment["deployment_id"])

    assert deployment["status"] == "READY_DISABLED"
    assert report["artifact_hash"]
    assert status["status"] == "VALIDATED"
    assert len(status["reports"]) == 1
    assert status["reports"][0]["summary"] == "Dry-run validation completed"


def test_gcs_transport_preserves_canonical_hmac_signature(tmp_path: Path, monkeypatch) -> None:
    catalog = _setup_repo(tmp_path)
    mirror_root = tmp_path / "gcs-mirror"
    monkeypatch.setenv("SVOS_PACKAGE_TRANSPORT", "gcs")
    monkeypatch.setenv("SVOS_GCS_BUCKET", "prod-strategy-artifacts")
    monkeypatch.setenv("SVOS_GCS_PREFIX", "packages")
    monkeypatch.setenv("SVOS_GCS_MIRROR_ROOT", str(mirror_root))

    service = DeploymentStatusService(root=tmp_path, catalog_path=catalog)
    package = service.build_strategy_package("ST-A2", actor="unit-test")
    deployment = service.create_deployment(strategy="ST-A2", actor="risk-operator")

    assert package["transport"] == "gcs"
    assert package["registry_uri"].startswith("gs://prod-strategy-artifacts/packages/ST-A2/2.1/")
    assert package["signature_scheme"] == "ed25519"
    assert package["signature_key_ref"] == "env:SVOS_PACKAGE_SIGNING_PRIVATE_KEY"
    assert Path(package["mirror_path"]).exists()
    assert deployment["package_transport"] == "gcs"
    assert deployment["package_registry_uri"] == package["registry_uri"]


def test_registry_inventory_and_rollback_history(tmp_path: Path) -> None:
    catalog = _setup_repo(tmp_path)
    service = DeploymentStatusService(root=tmp_path, catalog_path=catalog)
    first = service.create_deployment(strategy="ST-A2", actor="risk-operator")

    rollback = service.create_rollback(
        first["deployment_id"],
        to_version="2.1",
        actor="risk-operator",
        reason="rollback drill",
    )
    inventory = service.registry_inventory()

    assert rollback["status"] == "READY_DISABLED"
    assert inventory["deployment_count"] == 2
    assert inventory["rollback_count"] == 1
    assert inventory["strategies"][0]["supported_symbols"] == ["EURUSD", "GBPUSD"]
