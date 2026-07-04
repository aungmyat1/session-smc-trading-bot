from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import yaml

from research_db.readiness import apply_spread_filter, check_database, check_symbol
from scripts.build_timeframes import OHLCV_SCHEMA
from src.features.sessions import crypto_session_labels, label_sessions


def _catalog(path: Path, asset_class: str = "forex") -> Path:
    path.write_text(yaml.safe_dump({"symbols": {"TEST": {"asset_class": asset_class}}}), encoding="utf-8")
    return path


def _raw_month(root: Path, month: str) -> None:
    year, number = month.split("-")
    path = root / "TEST" / year / number / "ticks.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({
        "timestamp_ms": [1], "ask": [1.1], "bid": [1.0], "ask_vol": [1.0], "bid_vol": [1.0],
    }).to_parquet(path, index=False)


def _candles(root: Path, months: list[str]) -> None:
    rows = []
    for month in months:
        rows.append({
            "timestamp_utc": pd.Timestamp(f"{month}-02T12:00:00Z"),
            "open": 1.0, "high": 1.2, "low": 0.9, "close": 1.1, "volume": 2.0,
            "ask_open": 1.01, "bid_open": 1.0, "spread_avg": 0.0001,
            "spread_max": 0.0002, "tick_count": 2,
        })
    path = root / "TEST" / "M1.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_parquet(path, schema=OHLCV_SCHEMA, index=False)


def test_full_period_processed_coverage_is_ready(tmp_path: Path) -> None:
    raw, processed = tmp_path / "raw", tmp_path / "processed"
    for month in ("2023-07", "2023-08", "2023-09"):
        _raw_month(raw, month)
    _candles(processed, ["2023-07", "2023-08", "2023-09"])
    report = check_database(
        ["TEST"], date(2023, 7, 1), date(2023, 9, 30),
        raw_root=raw, processed_root=processed, catalog_path=_catalog(tmp_path / "symbols.yaml"),
    )
    assert report["status"] == "READY"
    assert report["blocking_error_count"] == 0


def test_missing_processed_month_is_blocking(tmp_path: Path) -> None:
    raw, processed = tmp_path / "raw", tmp_path / "processed"
    for month in ("2023-07", "2023-08"):
        _raw_month(raw, month)
    _candles(processed, ["2023-07"])
    result = check_symbol(
        "TEST", date(2023, 7, 1), date(2023, 8, 31),
        raw_root=raw, processed_root=processed, catalog_path=_catalog(tmp_path / "symbols.yaml"),
    )
    assert result.missing_processed_months == ["2023-08"]
    assert "missing processed symbol-month coverage" in result.errors


def test_warning_classification_and_crypto_calendar(tmp_path: Path) -> None:
    raw, processed = tmp_path / "raw", tmp_path / "processed"
    _raw_month(raw, "2023-07")
    _candles(processed, ["2023-07"])
    forex = check_symbol(
        "TEST", date(2023, 7, 1), date(2023, 7, 31), raw_root=raw,
        processed_root=processed, catalog_path=_catalog(tmp_path / "forex.yaml"),
    )
    assert set(forex.warnings) >= {"sunday_forex_reopen", "invalid_weekend_bars", "intraday_gaps"}

    labels = crypto_session_labels("2023-07-08T14:00:00Z")
    assert {"24_7", "Weekend", "Overlap", "London", "NewYork"}.issubset(labels)
    frame = pd.DataFrame({"timestamp": ["2023-07-08T14:00:00Z"]})
    assert "Weekend" in label_sessions(frame, pair="BTCUSDT", session_model="crypto_24_7").iloc[0]["session"]


def test_research_spread_filter_is_explicit_and_configurable() -> None:
    frame = pd.DataFrame({"spread_avg": [0.1, 0.6], "close": [1.0, 2.0]})
    assert apply_spread_filter(frame, None).shape[0] == 2
    assert apply_spread_filter(frame, 0.5)["close"].tolist() == [1.0]
