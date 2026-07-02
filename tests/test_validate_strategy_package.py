from __future__ import annotations

from pathlib import Path

from scripts.validate_strategy_package import validate_archive
from svos.deployment.service import DeploymentStatusService


def test_release_validator_accepts_generated_package(tmp_path: Path) -> None:
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
    approved: true
    version: 1.0.0
    strategy_spec_path: docs/spec.md
""",
        encoding="utf-8",
    )
    package = DeploymentStatusService(root=tmp_path, catalog_path=catalog).build_strategy_package("Test")

    result = validate_archive(Path(package["archive_path"]))

    assert result["valid"] is True
