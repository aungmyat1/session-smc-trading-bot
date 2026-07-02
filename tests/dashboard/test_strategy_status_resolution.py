from __future__ import annotations

import json
from pathlib import Path

import pytest

from dashboard import strategy_service


def test_svos_precedence_over_overlay(tmp_path, monkeypatch):
    name = "TEST-STRAT"
    meta = {"status": "backtest", "display_name": "Test Strat"}
    overlay = {"strategies": {name: {"status": "Overlay Status"}}}

    # create fake svos run dir with run_summary.json
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True)
    run_summary = {"latest_passed_stage": "statistical_validation", "generated_at": "2026-07-01T00:00:00Z"}
    (run_dir / "run_summary.json").write_text(json.dumps(run_summary))

    monkeypatch.setattr(strategy_service, "_latest_svos_run", lambda s: run_dir)

    result = strategy_service._catalog_meta_to_strategy(name, meta, overlay)
    assert result["status"] == strategy_service._STATUS_TO_UI_STAGE["statistical_validation"]


def test_catalog_used_when_no_svos_or_overlay(tmp_path, monkeypatch):
    name = "CAT-ONLY"
    meta = {"status": "replay", "display_name": "Cat Only"}
    overlay = {"strategies": {}}

    monkeypatch.setattr(strategy_service, "_latest_svos_run", lambda s: None)

    result = strategy_service._catalog_meta_to_strategy(name, meta, overlay)
    assert result["status"] == strategy_service._STATUS_TO_UI_STAGE["replay"]


def test_overlay_used_when_no_svos_and_no_catalog_status(tmp_path, monkeypatch):
    name = "OVR-ONLY"
    meta = {}
    overlay = {"strategies": {name: {"status": "Overlay Only", "name": "Ovr"}}}

    monkeypatch.setattr(strategy_service, "_latest_svos_run", lambda s: None)

    result = strategy_service._catalog_meta_to_strategy(name, meta, overlay)
    assert result["status"] == "Overlay Only"
