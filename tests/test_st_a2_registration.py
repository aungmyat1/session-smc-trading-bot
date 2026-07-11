from __future__ import annotations

from pathlib import Path

import yaml

from research.st_a2_freeze import STRATEGY_CONFIG, registration_manifest


def test_st_a2_strategy_definition_is_frozen() -> None:
    payload = yaml.safe_load(STRATEGY_CONFIG.read_text(encoding="utf-8"))

    assert payload["strategy_id"] == "ST-A2"
    assert payload["version"] == "1.0"
    assert payload["status"]["frozen"] is True
    assert payload["dataset"]["version"] == "professional_3y_4symbol_v2"


def test_st_a2_registration_manifest_has_hashes() -> None:
    manifest = registration_manifest()

    assert manifest["status"] == "FROZEN"
    assert manifest["strategy_hash"]
    assert manifest["configuration_hash"]
    assert manifest["dataset_hash"]
    assert len(manifest["strategy_hash"]) == 64
