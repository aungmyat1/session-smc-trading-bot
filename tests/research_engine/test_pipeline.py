from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.pipeline import ResearchEngine, ResearchPaths


def test_research_engine_builds_symbol(tmp_path):
    raw_root = tmp_path / "raw"
    raw_root.mkdir()
    raw_file = raw_root / "EURUSD_M1.csv"
    frame = pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01T08:00:00Z", periods=6, freq="1min", tz="UTC"),
            "open": [1.0, 1.0, 1.01, 1.02, 1.03, 1.04],
            "high": [1.01, 1.02, 1.05, 1.06, 1.07, 1.08],
            "low": [0.99, 0.97, 1.00, 1.01, 1.02, 1.03],
            "close": [1.0, 1.015, 1.035, 1.045, 1.055, 1.065],
            "volume": [100] * 6,
            "spread": [1.0] * 6,
        }
    )
    frame.to_csv(raw_file, index=False)

    engine = ResearchEngine(
        ResearchPaths(raw_root=raw_root, parquet_root=tmp_path / "parquet", duckdb_path=tmp_path / "research.db")
    )
    result = engine.build_symbol("EURUSD", timeframe="M1")
    assert "signals" in result
    assert (tmp_path / "parquet" / "EURUSD" / "candles.parquet").exists()
    assert (tmp_path / "research.db").exists()

