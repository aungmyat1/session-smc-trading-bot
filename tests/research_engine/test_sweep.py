from __future__ import annotations

import pandas as pd

from src.analytics.sweep import SweepCandidate, run_parameter_sweep


def test_parameter_sweep_returns_summary(tmp_path):
    raw_root = tmp_path / "raw"
    raw_root.mkdir()
    pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01T08:00:00Z", periods=8, freq="15min", tz="UTC"),
            "open": [1.0, 1.0, 1.01, 1.02, 1.03, 1.04, 1.05, 1.06],
            "high": [1.01, 1.02, 1.05, 1.06, 1.07, 1.08, 1.09, 1.10],
            "low": [0.99, 0.97, 1.00, 1.01, 1.02, 1.03, 1.04, 1.05],
            "close": [1.0, 1.015, 1.035, 1.045, 1.055, 1.065, 1.075, 1.085],
            "volume": [100] * 8,
            "spread": [1.0] * 8,
        }
    ).to_csv(raw_root / "EURUSD_M1.csv", index=False)

    summary = run_parameter_sweep(
        raw_root,
        "EURUSD",
        [
            SweepCandidate(name="baseline"),
            SweepCandidate(name="strict", signal={"min_confluence": 2, "max_signals_per_day": 1}),
        ],
        parquet_root=tmp_path / "parquet",
        duckdb_path=tmp_path / "research.db",
    )

    assert len(summary) == 2
    assert {"candidate", "n_trades", "avg_r", "expectancy", "profit_factor"}.issubset(summary.columns)
