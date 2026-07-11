"""Regression tests for StrategyRegistryService, the sanctioned registry API.

TASK-1-DAYTRADING-GOV exercised this service's ``record_version`` to
retroactively sync a registry entry that pre-existed a catalog entry
(the exact `DayTradingManeuvers` situation: a registry folder created by a
prior bootstrap run before the strategy had a `config/strategy_catalog.yaml`
row). These tests cover that path so it stays regression-tested going
forward, not just exercised once by hand.
"""

from __future__ import annotations

import json

import pytest

from svos.registry.service import StrategyRegistryService


def _write_catalog(root, strategies: dict) -> None:
    import yaml

    catalog_path = root / "config" / "strategy_catalog.yaml"
    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    catalog_path.write_text(
        yaml.safe_dump({"current_strategy": None, "strategies": strategies}, sort_keys=False),
        encoding="utf-8",
    )


def test_ensure_strategy_requires_catalog_entry(tmp_path):
    """A strategy with no catalog row cannot be registered — catalog is authoritative input."""
    _write_catalog(tmp_path, {})
    svc = StrategyRegistryService(root=tmp_path)
    with pytest.raises(KeyError):
        svc.ensure_strategy("Ghost")


def test_ensure_strategy_creates_registry_folder_via_service(tmp_path):
    """Registering a fresh strategy goes through the service, never a hand-written file."""
    _write_catalog(
        tmp_path,
        {"NewStrat": {"status": "draft", "svos_stage": "INTAKE", "approved": False, "version": "0.1"}},
    )
    svc = StrategyRegistryService(root=tmp_path)
    record = svc.ensure_strategy("NewStrat")

    assert record.current_stage == "INTAKE"
    assert record.legacy_status == "draft"
    assert record.version_count == 1

    state_path = tmp_path / "data" / "svos" / "registry" / "NewStrat" / "state.json"
    assert state_path.exists()
    on_disk = json.loads(state_path.read_text(encoding="utf-8"))
    assert on_disk["current_stage"] == "INTAKE"


def test_record_version_backfills_registry_entry_that_predates_catalog_row(tmp_path):
    """
    Simulates the DayTradingManeuvers scenario: a registry directory already
    exists (created before the strategy had a catalog entry) with a
    ``legacy_status`` that disagrees with the manifest a new catalog entry
    would carry. Adding the catalog row and calling ``record_version`` (the
    proper API — never a hand-edited JSON file) must reconcile
    ``legacy_status`` while preserving the already-reached ``current_stage``.
    """
    registry_dir = tmp_path / "data" / "svos" / "registry" / "OrphanStrat"
    registry_dir.mkdir(parents=True)
    (registry_dir / "versions.jsonl").write_text(
        json.dumps(
            {
                "actor": "system",
                "created_at": "2026-07-03T00:00:00+00:00",
                "manifest": {"status": "shadow", "version": "0.1"},
                "reason": "bootstrap",
                "strategy": "OrphanStrat",
                "version": "0.1",
                "version_id": "deadbeef",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (registry_dir / "state.json").write_text(
        json.dumps(
            {
                "current_stage": "INTAKE",
                "current_version_id": "deadbeef",
                "latest_version": "0.1",
                "legacy_status": "shadow",
                "strategy": "OrphanStrat",
                "updated_at": "2026-07-03T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )

    # Catalog entry did not exist until now — this is the governance fix.
    _write_catalog(
        tmp_path,
        {
            "OrphanStrat": {
                "status": "draft",
                "svos_stage": "INTAKE",
                "approved": False,
                "execution_allowed": False,
                "version": "0.1",
            }
        },
    )

    svc = StrategyRegistryService(root=tmp_path)

    # Before reconciliation: on-disk state still disagrees with the new catalog row.
    stale_state = json.loads((registry_dir / "state.json").read_text(encoding="utf-8"))
    assert stale_state["legacy_status"] == "shadow"

    record = svc.record_version(
        "OrphanStrat",
        actor="pm-agent-task-1",
        reason="TASK-1-DAYTRADING-GOV: catalog entry backfilled",
    )
    assert record.version_id != "deadbeef"

    reconciled = svc.get_strategy_record("OrphanStrat")
    assert reconciled.legacy_status == "draft"
    assert reconciled.current_stage == "INTAKE"  # stage is untouched — registration, not promotion
    assert reconciled.version_count == 2

    on_disk = json.loads((registry_dir / "state.json").read_text(encoding="utf-8"))
    assert on_disk["legacy_status"] == "draft"
    assert on_disk["current_stage"] == "INTAKE"
    assert on_disk["current_version_id"] == record.version_id


def test_summary_only_lists_strategies_present_in_catalog(tmp_path):
    """The registry audit (scripts/registry_audit.py) sources its list from the catalog."""
    registry_dir = tmp_path / "data" / "svos" / "registry" / "UncatalogedStrat"
    registry_dir.mkdir(parents=True)
    (registry_dir / "state.json").write_text(
        json.dumps({"strategy": "UncatalogedStrat", "current_stage": "INTAKE"}), encoding="utf-8"
    )
    _write_catalog(tmp_path, {})

    svc = StrategyRegistryService(root=tmp_path)
    summary = svc.summary()

    assert summary["strategy_count"] == 0
    names = [item["strategy"] for item in summary["strategies"]]
    assert "UncatalogedStrat" not in names
