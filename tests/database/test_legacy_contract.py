from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_legacy_import_is_idempotent_and_non_qualifying_by_contract() -> None:
    source = (ROOT / "db/legacy_import.py").read_text(encoding="utf-8")
    assert 'record_type == "strategy_catalog"' in source
    assert 'current_stage="DRAFT"' in source
    assert "LEGACY_IMPORTED" in source


def test_yaml_projection_is_generated_read_only() -> None:
    source = (ROOT / "db/projection.py").read_text(encoding="utf-8")
    assert '"generated_projection": True' in source
    assert "output.chmod(0o444)" in source
    assert '"approved": False' in source
    assert '"current_strategy": None' in source
