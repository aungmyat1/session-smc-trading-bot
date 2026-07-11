from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from research.professional_dataset_v2.pipeline import build_cost_models


def test_build_cost_models_writes_spread_percentiles(tmp_path: Path) -> None:
    tick = tmp_path / "tick" / "EURUSD" / "year=2026" / "month=01" / "day=01"
    tick.mkdir(parents=True)
    frame = pd.DataFrame(
        {
            "timestamp_utc": pd.date_range("2026-01-01", periods=5, freq="h", tz="UTC"),
            "symbol": ["EURUSD"] * 5,
            "bid": [1.0] * 5,
            "ask": [1.1, 1.2, 1.3, 1.4, 1.5],
            "spread": [0.1, 0.2, 0.3, 0.4, 0.5],
            "volume": [1.0] * 5,
            "year": [2026] * 5,
            "month": [1] * 5,
            "day": [1] * 5,
        }
    )
    pq.write_table(pa.Table.from_pandas(frame, preserve_index=False), tick / "ticks.parquet", compression="snappy")

    build_cost_models(tmp_path / "tick", tmp_path / "cost_models", ["EURUSD", "BTCUSD"])

    model = json.loads((tmp_path / "cost_models" / "EURUSD.json").read_text())
    assert model["spread_p50"] == 0.3
    assert (tmp_path / "cost_models" / "commission_model.yaml").exists()

