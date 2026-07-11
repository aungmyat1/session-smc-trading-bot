from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from research.professional_dataset_v2.pipeline import QualityThresholds, dataset_quality


def _write_bars(path: Path, rows: int = 8) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ts = pd.date_range("2026-01-01", periods=rows, freq="15min", tz="UTC")
    frame = pd.DataFrame(
        {
            "timestamp_utc": ts,
            "open": [1.0 + i for i in range(rows)],
            "high": [1.2 + i for i in range(rows)],
            "low": [0.9 + i for i in range(rows)],
            "close": [1.1 + i for i in range(rows)],
            "volume": [100.0] * rows,
        }
    )
    pq.write_table(pa.Table.from_pandas(frame, preserve_index=False), path, compression="snappy")


def test_dataset_quality_passes_clean_parquet(tmp_path: Path) -> None:
    root = tmp_path / "processed"
    _write_bars(root / "EURUSD" / "M15.parquet")
    output = tmp_path / "quality.json"

    report = dataset_quality(root, output, QualityThresholds())

    assert report["status"] == "PASS"
    assert json.loads(output.read_text())["files"][0]["duplicate_pct"] == 0.0


def test_dataset_quality_fails_duplicate_timestamps(tmp_path: Path) -> None:
    root = tmp_path / "processed"
    _write_bars(root / "EURUSD" / "M15.parquet")
    frame = pd.read_parquet(root / "EURUSD" / "M15.parquet")
    frame.loc[1, "timestamp_utc"] = frame.loc[0, "timestamp_utc"]
    pq.write_table(pa.Table.from_pandas(frame, preserve_index=False), root / "EURUSD" / "M15.parquet", compression="snappy")

    report = dataset_quality(root, tmp_path / "quality.json", QualityThresholds())

    assert report["status"] == "FAIL"

