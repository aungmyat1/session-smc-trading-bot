from __future__ import annotations

import json
from pathlib import Path

import yaml

from scripts.validate_strategy_identity import validate_strategy_identity


def _identity_tree(tmp_path: Path, *, package_id: str = "ST-A2", registry_id: str = "ST-A2") -> Path:
    config = tmp_path / "config"
    config.mkdir()
    (config / "strategy_catalog.yaml").write_text(yaml.safe_dump({"strategies": {"ST-A2": {"version": "2.1"}}}), encoding="utf-8")
    (config / "strategy_portfolio.yaml").write_text(yaml.safe_dump({"strategies": {"ST-A2": {"enabled": True}}}), encoding="utf-8")
    state = tmp_path / "data" / "svos" / "registry" / "ST-A2" / "state.json"
    state.parent.mkdir(parents=True)
    state.write_text(json.dumps({"strategy": registry_id}), encoding="utf-8")
    package = tmp_path / "package"
    package.mkdir()
    (package / "strategy_spec.yaml").write_text(yaml.safe_dump({"strategy_id": package_id}), encoding="utf-8")
    (package / "approval_status.json").write_text(json.dumps({"approval_status": "APPROVED"}), encoding="utf-8")
    return package


def test_identity_validation_passes_when_all_sources_match(tmp_path: Path) -> None:
    package = _identity_tree(tmp_path)
    result = validate_strategy_identity(root=tmp_path, package_path=package, runner_strategy_id="ST-A2")
    assert result.valid
    assert not result.mismatches


def test_identity_validation_returns_catalog_spelling(tmp_path: Path) -> None:
    package = _identity_tree(tmp_path)
    result = validate_strategy_identity(root=tmp_path, package_path=package, runner_strategy_id="st_a2")
    assert result.valid
    assert result.strategy_id == "ST-A2"


def test_package_identity_mismatch_is_reported(tmp_path: Path) -> None:
    package = _identity_tree(tmp_path, package_id="NYMomentum")
    result = validate_strategy_identity(root=tmp_path, package_path=package, runner_strategy_id="ST-A2")
    assert not result.valid
    assert any("approved_package identity" in mismatch for mismatch in result.mismatches)
    assert "ST-A2" in result.recommended_fix


def test_registry_identity_mismatch_is_reported(tmp_path: Path) -> None:
    package = _identity_tree(tmp_path, registry_id="ST-A3")
    result = validate_strategy_identity(root=tmp_path, package_path=package, runner_strategy_id="ST-A2")
    assert not result.valid
    assert any("svos_registry identity" in mismatch for mismatch in result.mismatches)


def test_missing_portfolio_identity_is_reported(tmp_path: Path) -> None:
    package = _identity_tree(tmp_path)
    (tmp_path / "config" / "strategy_portfolio.yaml").write_text("strategies: {}\n", encoding="utf-8")
    result = validate_strategy_identity(root=tmp_path, package_path=package, runner_strategy_id="ST-A2")
    assert not result.valid
    assert "portfolio identity is missing" in result.mismatches


def test_st_a2_entrypoint_is_explicitly_legacy() -> None:
    from scripts import run_st_a2_demo

    assert run_st_a2_demo.LEGACY_ENTRYPOINT is True
