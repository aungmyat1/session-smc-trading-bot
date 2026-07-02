from __future__ import annotations

from typing import Any


def reconcile_positions(broker: list[dict[str, Any]], journal: list[dict[str, Any]]) -> dict[str, list[str]]:
    broker_ids = {str(item.get("id")) for item in broker}
    journal_ids = {str(item.get("id")) for item in journal}
    return {"orphan_broker": sorted(broker_ids - journal_ids), "missing_broker": sorted(journal_ids - broker_ids)}
