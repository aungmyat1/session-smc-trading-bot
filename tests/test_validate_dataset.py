from __future__ import annotations

import pandas as pd

import scripts.validate_dataset as validate_dataset


def _write_ticks(path, timestamps):
    frame = pd.DataFrame(
        {
            "timestamp_ms": [int(ts.value // 10**6) for ts in timestamps],
            "ask": [1.1001] * len(timestamps),
            "bid": [1.1000] * len(timestamps),
            "ask_vol": [1.0] * len(timestamps),
            "bid_vol": [1.0] * len(timestamps),
        }
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path, index=False)


def _write_bars(path, timestamps):
    frame = pd.DataFrame(
        {
            "timestamp_utc": timestamps,
            "open": [1.1] * len(timestamps),
            "high": [1.2] * len(timestamps),
            "low": [1.0] * len(timestamps),
            "close": [1.1] * len(timestamps),
            "volume": [10.0] * len(timestamps),
            "ask_open": [1.1001] * len(timestamps),
            "bid_open": [1.1000] * len(timestamps),
            "spread_avg": [0.0001] * len(timestamps),
            "spread_max": [0.0002] * len(timestamps),
            "tick_count": [5] * len(timestamps),
        }
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path, index=False)


def test_compute_month_coverage_detects_missing_months():
    coverage = validate_dataset.compute_month_coverage(
        [(2024, 1), (2024, 3)],
        expected_start=(2024, 1),
        expected_end=(2024, 3),
    )

    assert coverage["coverage"] == 2 / 3
    assert coverage["missing_months"] == [(2024, 2)]


def test_validate_raw_and_partitioned_market_reports_coverage(tmp_path, monkeypatch):
    raw_root = tmp_path / "raw"
    proc_root = tmp_path / "processed"
    market_root = tmp_path / "market"

    _write_ticks(
        raw_root / "EURUSD" / "2024" / "01" / "ticks.parquet",
        pd.to_datetime(["2024-01-02T00:00:00Z", "2024-01-02T01:00:00Z"], utc=True),
    )
    _write_ticks(
        raw_root / "EURUSD" / "2024" / "03" / "ticks.parquet",
        pd.to_datetime(["2024-03-02T00:00:00Z"], utc=True),
    )

    _write_bars(
        market_root / "m15" / "EURUSD" / "year=2024" / "month=01" / "part-000.parquet",
        pd.to_datetime(["2024-01-02T00:00:00Z", "2024-01-02T00:15:00Z"], utc=True),
    )

    monkeypatch.setattr(validate_dataset, "DATA_RAW", raw_root)
    monkeypatch.setattr(validate_dataset, "DATA_PROC", proc_root)
    monkeypatch.setattr(validate_dataset, "DATA_MARKET", market_root)

    report = validate_dataset.ValidationReport()
    raw_stats = validate_dataset.validate_raw_ticks(
        "EURUSD",
        report,
        expected_start=(2024, 1),
        expected_end=(2024, 3),
    )
    processed_stats = validate_dataset.validate_processed("EURUSD", "M15", report)

    assert raw_stats["coverage"] == 2 / 3
    assert raw_stats["missing_months"] == [(2024, 2)]
    assert processed_stats["schema_ok"] is True
    assert processed_stats["sorted"] is True
    assert processed_stats["duplicates"] == 0
    assert any("coverage 2/3 months" in message for _, message in report.sections)


def test_summarize_acquisition_reads_month_sidecars(tmp_path, monkeypatch):
    raw_root = tmp_path / "raw"
    month_dir = raw_root / "EURUSD" / "2024" / "01"
    month_dir.mkdir(parents=True, exist_ok=True)
    month_dir.joinpath("acquisition.json").write_text(
        """
        {
          "symbol": "EURUSD",
          "year": 2024,
          "month": 1,
          "month_key": "2024-01",
          "rows": 1500,
          "elapsed_seconds": 3.0,
          "rows_per_second": 500.0,
          "retries": 4,
          "hours_ok": 10,
          "hours_missing": 5,
          "hours_failed": 1
        }
        """,
        encoding="utf-8",
    )

    monkeypatch.setattr(validate_dataset, "DATA_RAW", raw_root)

    summary = validate_dataset.summarize_acquisition("EURUSD")

    assert summary is not None
    assert summary["months"] == 1
    assert summary["rows"] == 1500
    assert summary["rows_per_second"] == 500.0
    assert summary["retries"] == 4
    assert summary["hours_ok"] == 10
    assert summary["hours_missing"] == 5
    assert summary["hours_failed"] == 1
