from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.research_feature_database import (FeatureDatabasePaths, annotate_fvg,
                                           annotate_liquidity_sweeps,
                                           annotate_order_blocks,
                                           annotate_structure,
                                           build_feature_database,
                                           detect_swings, label_sessions)


def _swing_candles() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                [
                    "2024-01-01T06:59:00Z",
                    "2024-01-01T07:00:00Z",
                    "2024-01-01T07:01:00Z",
                    "2024-01-01T07:02:00Z",
                    "2024-01-01T07:03:00Z",
                ],
                utc=True,
            ),
            "pair": ["EURUSD"] * 5,
            "open": [1.00, 1.01, 1.02, 1.03, 1.04],
            "high": [1.01, 1.02, 1.10, 1.03, 1.02],
            "low": [0.99, 0.98, 0.97, 1.00, 1.01],
            "close": [1.00, 1.01, 1.03, 1.02, 1.01],
            "volume": [100] * 5,
        }
    )


def _structure_candles() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                [
                    "2024-01-01T06:59:00Z",
                    "2024-01-01T07:00:00Z",
                    "2024-01-01T07:01:00Z",
                    "2024-01-01T07:02:00Z",
                    "2024-01-01T07:03:00Z",
                    "2024-01-01T07:04:00Z",
                    "2024-01-01T07:05:00Z",
                ],
                utc=True,
            ),
            "pair": ["EURUSD"] * 7,
            "open": [1.00, 1.01, 1.02, 1.03, 1.02, 1.01, 0.99],
            "high": [1.01, 1.02, 1.10, 1.04, 1.03, 1.02, 1.00],
            "low": [0.99, 0.98, 0.97, 1.03, 0.94, 0.95, 0.94],
            "close": [1.00, 1.00, 1.11, 1.02, 0.98, 0.97, 0.93],
            "volume": [100] * 7,
        }
    )


def test_session_labels_cover_london_and_new_york():
    out = label_sessions(_structure_candles())
    assert out.loc[0, "session"] == "None"
    assert out.loc[1, "session"] == "London"


def test_detect_swings_marks_center_pivot():
    candles = _swing_candles()
    swings = detect_swings(candles, n=1)
    assert bool(swings.loc[2, "swing_high"]) is True
    assert bool(swings.loc[2, "swing_low"]) is True


def test_structure_sweep_ob_and_fvg_annotations():
    candles = detect_swings(_structure_candles(), n=1)
    structured = annotate_structure(candles)
    swept = annotate_liquidity_sweeps(structured)
    ordered = annotate_order_blocks(swept)
    fvgs = annotate_fvg(ordered)

    assert bool(fvgs["bos"].any()) is True
    assert bool(fvgs["choch"].any()) is True
    assert (
        bool(fvgs["sweep_high"].any()) is True or bool(fvgs["sweep_low"].any()) is True
    )
    assert bool(fvgs["has_order_block"].any()) is True
    assert bool(fvgs["has_fvg"].any()) is True


def test_build_feature_database_writes_outputs(tmp_path: Path):
    raw_root = tmp_path / "raw"
    processed_root = tmp_path / "processed"
    output_root = tmp_path / "research_db"
    raw_root.mkdir()
    processed_root.mkdir(parents=True, exist_ok=True)

    frame = _structure_candles()
    frame.to_csv(raw_root / "EURUSD_M1.csv", index=False)

    outputs = build_feature_database(
        ["EURUSD"],
        paths=FeatureDatabasePaths(
            raw_root=raw_root, processed_root=processed_root, output_root=output_root
        ),
        swing_lookback=1,
    )

    assert "feature_database" in outputs
    assert len(outputs["feature_database"]) == len(frame)
    assert (output_root / "feature_database.parquet").exists()
    assert (output_root / "feature_database.duckdb").exists()
    assert (output_root / "data" / "processed" / "candles_labeled.parquet").exists()
