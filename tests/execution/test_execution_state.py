from __future__ import annotations

import pytest

from execution.execution_state import ExecutionStateStore


def test_execution_state_store_persists_timeline(tmp_path):
    store = ExecutionStateStore(tmp_path)

    record = store.create_record(strategy_id="ST-A2", strategy_version="1.0", signal_id="sig-1")
    store.transition(record.execution_id, "GOVERNANCE_VALIDATED", metadata={"allowed": True})
    store.transition(record.execution_id, "PERMISSION_VALIDATED", metadata={"mode": "NORMAL"})

    timeline = store.timeline(record.execution_id)

    assert [item["state"] for item in timeline] == [
        "SIGNAL_RECEIVED",
        "GOVERNANCE_VALIDATED",
        "PERMISSION_VALIDATED",
    ]


def test_execution_state_store_rejects_illegal_transition(tmp_path):
    store = ExecutionStateStore(tmp_path)
    record = store.create_record(strategy_id="ST-A2", strategy_version="1.0", signal_id="sig-2")

    with pytest.raises(ValueError, match="illegal execution transition"):
        store.transition(record.execution_id, "COMPLETED")
