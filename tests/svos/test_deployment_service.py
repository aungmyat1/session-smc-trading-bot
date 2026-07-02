from __future__ import annotations

import json
import tarfile
from pathlib import Path

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
    assert manifest["package_format"] == "strategy-package/v1"
    assert manifest["live_trading_enabled"] is False

    with tarfile.open(Path(package["archive_path"]), "r:gz") as archive:
        names = sorted(archive.getnames())
    assert "manifest.json" in names
    assert "catalog_manifest.json" in names
    assert "strategy_spec.md" in names
    assert "validations.json" in names


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


def test_gcs_transport_and_kms_style_signing_contracts_can_be_enabled_with_env(tmp_path: Path, monkeypatch) -> None:
    catalog = _setup_repo(tmp_path)
    mirror_root = tmp_path / "gcs-mirror"
    monkeypatch.setenv("SVOS_PACKAGE_TRANSPORT", "gcs")
    monkeypatch.setenv("SVOS_GCS_BUCKET", "prod-strategy-artifacts")
    monkeypatch.setenv("SVOS_GCS_PREFIX", "packages")
    monkeypatch.setenv("SVOS_GCS_MIRROR_ROOT", str(mirror_root))
    monkeypatch.setenv(
        "SVOS_KMS_KEY_VERSION",
        "projects/demo/locations/global/keyRings/svos/cryptoKeys/strategy/cryptoKeyVersions/1",
    )

    service = DeploymentStatusService(root=tmp_path, catalog_path=catalog)
    package = service.build_strategy_package("ST-A2", actor="unit-test")
    deployment = service.create_deployment(strategy="ST-A2", actor="risk-operator")

    assert package["transport"] == "gcs"
    assert package["registry_uri"].startswith("gs://prod-strategy-artifacts/packages/ST-A2/2.1/")
    assert package["signature_scheme"] == "gcp-kms-asymmetric-attestation"
    assert package["signature_key_ref"].endswith("/cryptoKeyVersions/1")
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
