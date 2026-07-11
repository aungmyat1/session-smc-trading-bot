from __future__ import annotations

import json

from research.st_a2_freeze import LEDGER_COLUMNS, LEDGER_DIR, LEDGER_MANIFEST, _ledger_hash, generate_baseline, load_ledgers


def test_st_a2_trade_ledger_schema_and_hashes() -> None:
    manifest = json.loads(LEDGER_MANIFEST.read_text(encoding="utf-8"))
    rows = load_ledgers(LEDGER_DIR)

    assert manifest["status"] == "FROZEN"
    assert manifest["trade_count"] == len(rows)
    assert manifest["ledger_hash"] == _ledger_hash(rows)

    trade_ids = [row["trade_id"] for row in rows]
    assert len(trade_ids) == len(set(trade_ids))

    for row in rows:
        assert set(LEDGER_COLUMNS).issubset(row.keys())
        assert row["dataset_hash"] == manifest["dataset_hash"]
        assert row["strategy_hash"] == manifest["strategy_hash"]


def test_st_a2_trade_ledger_reproducible() -> None:
    before_manifest = json.loads(LEDGER_MANIFEST.read_text(encoding="utf-8"))
    before_rows = load_ledgers(LEDGER_DIR)

    result = generate_baseline(overwrite=True)
    after_manifest = json.loads(LEDGER_MANIFEST.read_text(encoding="utf-8"))
    after_rows = load_ledgers(LEDGER_DIR)

    assert result["trade_count"] == before_manifest["trade_count"]
    assert after_manifest["trade_count"] == before_manifest["trade_count"]
    assert after_manifest["ledger_hash"] == before_manifest["ledger_hash"]
    assert _ledger_hash(after_rows) == _ledger_hash(before_rows)
