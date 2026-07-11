from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from research.professional_dataset_v2.pipeline import create_manifest, generate_checksums, refresh_plan


def test_manifest_checksums_and_refresh_plan(tmp_path: Path, monkeypatch) -> None:
    import research.professional_dataset_v2.pipeline as pipeline

    monkeypatch.setattr(pipeline, "ROOT", tmp_path)
    processed = tmp_path / "data" / "processed" / "EURUSD"
    processed.mkdir(parents=True)
    frame = pd.DataFrame(
        {
            "timestamp_utc": pd.date_range("2026-01-01", periods=2, freq="15min", tz="UTC"),
            "open": [1.0, 1.1],
            "high": [1.2, 1.3],
            "low": [0.9, 1.0],
            "close": [1.1, 1.2],
        }
    )
    pq.write_table(pa.Table.from_pandas(frame, preserve_index=False), processed / "M15.parquet", compression="snappy")
    quality = tmp_path / "artifacts" / "data_quality_report.json"
    quality.parent.mkdir(parents=True)
    quality.write_text(json.dumps({"status": "PASS", "files": []}))
    config = {
        "dataset_id": "professional_3y_4symbol_v2",
        "symbols": ["EURUSD"],
        "timeframes": ["M15"],
        "processed_root": "data/processed",
        "window": {"start": "2026-01", "end": "2026-01"},
        "sources": {},
    }

    manifest = create_manifest(config, tmp_path / "datasets" / "professional_3y_4symbol_v2", quality)
    checksums = generate_checksums(tmp_path / "datasets" / "professional_3y_4symbol_v2")
    plan = refresh_plan(config, tmp_path / "data" / "tick", tmp_path / "datasets" / "professional_3y_4symbol_v2" / "checksums.json")

    assert manifest["record_counts"]["EURUSD"]["M15"] == 2
    assert checksums["dataset_hash"]
    assert plan["actions"][0]["action"] == "download_month"
