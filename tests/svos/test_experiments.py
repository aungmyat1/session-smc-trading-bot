"""Tests for svos.experiments.manager.ExperimentManager."""

from __future__ import annotations

from pathlib import Path

import pytest

from svos.experiments.manager import ExperimentManager, ExperimentRecord


@pytest.fixture()
def mgr(tmp_path: Path) -> ExperimentManager:
    return ExperimentManager(tmp_path)


def test_register_returns_record(mgr: ExperimentManager) -> None:
    rec = mgr.register("ST-A2", "Wider SL reduces false exits", {"sl_pips": 3}, actor="quant")
    assert isinstance(rec, ExperimentRecord)
    assert rec.strategy == "ST-A2"
    assert rec.status == "PENDING"
    assert rec.experiment_id


def test_register_idempotent(mgr: ExperimentManager) -> None:
    rec1 = mgr.register("ST-A2", "Same hypothesis", {"sl_pips": 3}, actor="quant")
    rec2 = mgr.register("ST-A2", "Same hypothesis", {"sl_pips": 3}, actor="quant")
    assert rec1.experiment_id == rec2.experiment_id


def test_experiment_id_differs_on_param_change(mgr: ExperimentManager) -> None:
    rec1 = mgr.register("ST-A2", "SL test", {"sl_pips": 3}, actor="quant")
    rec2 = mgr.register("ST-A2", "SL test", {"sl_pips": 4}, actor="quant")
    assert rec1.experiment_id != rec2.experiment_id


def test_complete_updates_status(mgr: ExperimentManager, tmp_path: Path) -> None:
    rec = mgr.register("ST-A2", "Test hypothesis", {"sl_pips": 2}, actor="quant")
    updated = mgr.complete(
        rec.experiment_id,
        run_id="run-001",
        status="FAIL",
        verdict="PF_2x < 1.0",
        metadata={"pf": 0.87},
    )
    assert updated.status == "FAIL"
    assert updated.run_id == "run-001"
    assert updated.verdict == "PF_2x < 1.0"
    assert updated.completed_at is not None
    assert updated.metadata["pf"] == 0.87


def test_complete_raises_on_invalid_status(mgr: ExperimentManager) -> None:
    rec = mgr.register("ST-A2", "Test", {}, actor="quant")
    with pytest.raises(ValueError, match="status"):
        mgr.complete(rec.experiment_id, run_id="x", status="INVALID", verdict="")


def test_complete_raises_on_unknown_id(mgr: ExperimentManager) -> None:
    with pytest.raises(KeyError):
        mgr.complete("nonexistent-id", run_id="x", status="PASS", verdict="ok")


def test_get_returns_most_recent(mgr: ExperimentManager) -> None:
    rec = mgr.register("ST-A2", "Fetch test", {}, actor="quant")
    mgr.complete(rec.experiment_id, run_id="r1", status="PASS", verdict="ok")
    fetched = mgr.get(rec.experiment_id)
    assert fetched.status == "PASS"


def test_get_raises_on_unknown(mgr: ExperimentManager) -> None:
    with pytest.raises(KeyError):
        mgr.get("does-not-exist")


def test_list_returns_all_strategies(mgr: ExperimentManager) -> None:
    mgr.register("ST-A2", "H1", {}, actor="quant")
    mgr.register("LondonBreakout", "H2", {}, actor="quant")
    results = mgr.list()
    strategies = {r["strategy"] for r in results}
    assert "ST-A2" in strategies
    assert "LondonBreakout" in strategies


def test_list_filters_by_strategy(mgr: ExperimentManager) -> None:
    mgr.register("ST-A2", "H1", {}, actor="quant")
    mgr.register("LondonBreakout", "H2", {}, actor="quant")
    results = mgr.list(strategy="ST-A2")
    assert all(r["strategy"] == "ST-A2" for r in results)
    assert len(results) == 1


def test_list_deduplicates_on_completion(mgr: ExperimentManager) -> None:
    rec = mgr.register("ST-A2", "Dedup test", {}, actor="quant")
    mgr.complete(rec.experiment_id, run_id="r1", status="FAIL", verdict="")
    results = mgr.list(strategy="ST-A2")
    # Should show only one entry (the latest), not two (register + complete)
    assert len(results) == 1
    assert results[0]["status"] == "FAIL"


def test_jsonl_is_append_only(mgr: ExperimentManager, tmp_path: Path) -> None:
    rec = mgr.register("ST-A2", "Append test", {}, actor="quant")
    path = tmp_path / "data" / "svos" / "experiments" / "ST-A2" / "experiments.jsonl"
    initial_lines = path.read_text().splitlines()
    assert len(initial_lines) == 1

    mgr.complete(rec.experiment_id, run_id="r1", status="PASS", verdict="all good")
    updated_lines = path.read_text().splitlines()
    # Both the original PENDING row and the PASS completion row are present
    assert len(updated_lines) == 2
    assert initial_lines[0] in updated_lines  # original preserved


def test_register_requires_nonempty_strategy(mgr: ExperimentManager) -> None:
    with pytest.raises(ValueError, match="strategy"):
        mgr.register("", "H", {}, actor="quant")


def test_register_requires_nonempty_hypothesis(mgr: ExperimentManager) -> None:
    with pytest.raises(ValueError, match="hypothesis"):
        mgr.register("ST-A2", "", {}, actor="quant")


def test_register_requires_nonempty_actor(mgr: ExperimentManager) -> None:
    with pytest.raises(ValueError, match="actor"):
        mgr.register("ST-A2", "H", {}, actor="")


def test_to_dict_serializable(mgr: ExperimentManager) -> None:
    import json
    rec = mgr.register("ST-A2", "Serialise test", {"x": 1}, actor="quant")
    assert json.dumps(rec.to_dict())
