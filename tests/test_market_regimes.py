from __future__ import annotations

from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from research.professional_dataset_v2.pipeline import generate_market_regimes


def test_generate_market_regimes_labels_session_opens(tmp_path: Path) -> None:
    processed = tmp_path / "processed" / "EURUSD"
    processed.mkdir(parents=True)
    ts = pd.date_range("2026-01-01 06:00", periods=16, freq="15min", tz="UTC")
    frame = pd.DataFrame(
        {
            "timestamp_utc": ts,
            "open": range(16),
            "high": [x + 1 for x in range(16)],
            "low": [x - 1 for x in range(16)],
            "close": [x + 0.5 for x in range(16)],
        }
    )
    pq.write_table(pa.Table.from_pandas(frame, preserve_index=False), processed / "M15.parquet", compression="snappy")

    generate_market_regimes(tmp_path / "processed", tmp_path / "regimes", ["EURUSD"])

    out = pd.read_parquet(tmp_path / "regimes" / "EURUSD.parquet")
    assert "LONDON_OPEN" in set(out["regime"])

