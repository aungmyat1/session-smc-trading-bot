from __future__ import annotations

from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from research.professional_dataset_v2.pipeline import extract_smc_events


def test_extract_smc_events_writes_bos_and_fvg(tmp_path: Path) -> None:
    processed = tmp_path / "processed" / "EURUSD"
    processed.mkdir(parents=True)
    rows = 30
    frame = pd.DataFrame(
        {
            "timestamp_utc": pd.date_range("2026-01-01", periods=rows, freq="15min", tz="UTC"),
            "open": [1.0] * rows,
            "high": [1.1] * 20 + [1.8] + [1.2] * 9,
            "low": [0.9] * rows,
            "close": [1.0] * 20 + [1.7] + [1.0] * 9,
        }
    )
    pq.write_table(pa.Table.from_pandas(frame, preserve_index=False), processed / "M15.parquet", compression="snappy")

    extract_smc_events(tmp_path / "processed", tmp_path / "events", ["EURUSD"])

    out = pd.read_parquet(tmp_path / "events" / "EURUSD.parquet")
    assert "BOS" in set(out["event_type"])
