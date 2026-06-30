from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.data.parquet_store import load_parquet, save_parquet
from src.data.validator import validate_candles


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                [
                    "2024-01-01T00:00:00Z",
                    "2024-01-01T00:01:00Z",
                    "2024-01-01T00:02:00Z",
                ],
                utc=True,
            ),
            "open": [1.0, 1.01, 1.02],
            "high": [1.01, 1.02, 1.03],
            "low": [0.99, 1.0, 1.01],
            "close": [1.005, 1.015, 1.025],
            "volume": [100, 110, 120],
            "spread": [1.0, 1.0, 1.0],
        }
    )


def test_validate_candles_passes_on_clean_data():
    report = validate_candles(_frame())
    assert report.ok is True
    assert report.stats["rows"] == 3


def test_validate_candles_flags_duplicates_and_bad_ohlc():
    df = _frame()
    df.loc[1, "timestamp"] = df.loc[0, "timestamp"]
    df.loc[2, "low"] = 2.0
    report = validate_candles(df)
    assert report.ok is False
    assert any("duplicate" in err for err in report.errors)
    assert any("invalid OHLC" in err for err in report.errors)


def test_validate_candles_tolerates_sparse_forex_gaps():
    df = _frame()
    df.loc[2, "timestamp"] = pd.Timestamp("2024-01-01T00:07:00Z")
    report = validate_candles(df)
    assert report.ok is True
    assert report.stats["gap_count"] == 1
    assert report.warnings


def test_parquet_round_trip(tmp_path: Path):
    path = tmp_path / "candles.parquet"
    saved = save_parquet(_frame(), path)
    loaded = load_parquet(saved)
    assert len(loaded) == 3
    assert list(loaded.columns) == [
        "timestamp",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "spread",
    ]
