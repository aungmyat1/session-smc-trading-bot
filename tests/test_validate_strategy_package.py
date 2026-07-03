from __future__ import annotations

from pathlib import Path

from scripts.validate_strategy_package import validate_archive
from svos.deployment.service import DeploymentStatusService


def test_release_validator_accepts_generated_package(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SVOS_PACKAGE_SIGNING_PRIVATE_KEY", "11" * 32)
    monkeypatch.setenv("SVOS_PACKAGE_VERIFYING_PUBLIC_KEY", "d04ab232742bb4ab3a1368bd4615e4e6d0224ab71a016baf8520a332c9778737")
    (tmp_path / "config").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "spec.md").write_text("# Strategy\n", encoding="utf-8")
    (tmp_path / "requirements.txt").write_text("locked\n", encoding="utf-8")
    catalog = tmp_path / "config" / "strategy_catalog.yaml"
    catalog.write_text(
        """current_strategy: Test
strategies:
  Test:
    status: production_approval
    svos_stage: PRODUCTION_APPROVAL
    approved: true
    approval:
      decision: APPROVED
      approved_at: "2026-01-01T00:00:00+00:00"
      expires_at: "2099-01-01T00:00:00+00:00"
      revoked: false
    adapter_id: Test
    adapter_version: 1.0.0
    parameters: {symbols: [EURUSD]}
    risk_policy: {policy_id: test-demo}
    evidence: [{stage: VIRTUAL_DEMO, status: PASS, artifact_hash: fixture}]
    version: 1.0.0
    strategy_spec_path: docs/spec.md
""",
        encoding="utf-8",
    )
    package = DeploymentStatusService(root=tmp_path, catalog_path=catalog).build_strategy_package("Test")

    result = validate_archive(Path(package["archive_path"]))

    assert result["valid"] is True
