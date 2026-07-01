from pathlib import Path

from shared.configuration import (
    default_catalog_path,
    default_validation_config_path,
    load_yaml_mapping,
    resolve_catalog_path,
    resolve_validation_config_path,
)


def test_load_yaml_mapping_returns_mapping(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text("alpha: 1\nbeta: two\n", encoding="utf-8")
    assert load_yaml_mapping(path) == {"alpha": 1, "beta": "two"}


def test_load_yaml_mapping_normalizes_missing_or_invalid_payload(tmp_path: Path) -> None:
    missing = tmp_path / "missing.yaml"
    assert load_yaml_mapping(missing, default={"ok": True}) == {"ok": True}

    invalid = tmp_path / "invalid.yaml"
    invalid.write_text("- item\n- item2\n", encoding="utf-8")
    assert load_yaml_mapping(invalid, default={"ok": True}) == {"ok": True}


def test_catalog_and_validation_path_helpers(tmp_path: Path) -> None:
    assert default_catalog_path(tmp_path) == tmp_path / "config" / "strategy_catalog.yaml"
    assert default_validation_config_path(tmp_path) == tmp_path / "config" / "validation.yaml"

    custom_catalog = tmp_path / "custom-catalog.yaml"
    custom_validation = tmp_path / "custom-validation.yaml"
    assert resolve_catalog_path(custom_catalog, root=tmp_path) == custom_catalog
    assert resolve_validation_config_path(custom_validation, root=tmp_path) == custom_validation
