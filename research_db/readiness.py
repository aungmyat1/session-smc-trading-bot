"""Read-only readiness checks for canonical research tick and M1 candle data."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq
import yaml

ROOT = Path(__file__).resolve().parents[1]
RAW_ROOT = ROOT / "data" / "raw" / "dukascopy"
PROCESSED_ROOT = ROOT / "data" / "processed"
CATALOG_PATH = ROOT / "config" / "symbols.yaml"
REQUIRED_RAW_COLUMNS = {"timestamp_ms", "ask", "bid", "ask_vol", "bid_vol"}
REQUIRED_CANDLE_COLUMNS = {
    "timestamp_utc", "open", "high", "low", "close", "volume",
    "ask_open", "bid_open", "spread_avg", "spread_max", "tick_count",
}
DEFAULT_SPREAD_LIMITS = {"EURUSD": 0.0010, "GBPUSD": 0.0012, "XAUUSD": 0.5}


def apply_spread_filter(frame: pd.DataFrame, max_spread: float | None) -> pd.DataFrame:
    """Apply an explicit research cost-quality filter; no limit means no filtering."""
    if max_spread is None:
        return frame.copy()
    if max_spread < 0:
        raise ValueError("max_spread must be non-negative")
    column = "spread_avg" if "spread_avg" in frame.columns else "spread_mean"
    if column not in frame.columns:
        raise ValueError("spread filter requires spread_avg or spread_mean")
    return frame.loc[frame[column] <= max_spread].copy()


def month_range(start: date, end: date) -> list[str]:
    current = start.replace(day=1)
    last = end.replace(day=1)
    result = []
    while current <= last:
        result.append(current.strftime("%Y-%m"))
        current = date(current.year + (current.month == 12), current.month % 12 + 1, 1)
    return result


@dataclass
class SymbolReadiness:
    symbol: str
    asset_class: str
    raw_months: list[str] = field(default_factory=list)
    processed_months: list[str] = field(default_factory=list)
    missing_raw_months: list[str] = field(default_factory=list)
    missing_processed_months: list[str] = field(default_factory=list)
    schema_valid: bool = False
    ohlc_valid: bool = False
    sorted: bool = False
    duplicates: int = 0
    warnings: Counter = field(default_factory=Counter)
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        payload = vars(self).copy()
        payload["warnings"] = dict(self.warnings)
        return payload


def _catalog(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))["symbols"]


def _raw_months(symbol: str, raw_root: Path) -> tuple[list[str], Counter]:
    found, warnings = [], Counter()
    for path in sorted((raw_root / symbol).glob("????/??/ticks.parquet")):
        label = f"{path.parent.parent.name}-{path.parent.name}"
        try:
            schema = set(pq.read_schema(path).names)
            if REQUIRED_RAW_COLUMNS.issubset(schema) and pq.read_metadata(path).num_rows > 0:
                found.append(label)
        except Exception:
            continue
        telemetry = path.with_name("acquisition.json")
        if telemetry.exists():
            try:
                data = json.loads(telemetry.read_text(encoding="utf-8"))
                if data.get("hours_missing", 0) or data.get("hours_failed", 0):
                    warnings["acquisition_hour_gaps"] += 1
            except (OSError, ValueError):
                warnings["acquisition_telemetry_invalid"] += 1
    return found, warnings


def check_symbol(
    symbol: str,
    start: date,
    end: date,
    *,
    raw_root: Path = RAW_ROOT,
    processed_root: Path = PROCESSED_ROOT,
    catalog_path: Path = CATALOG_PATH,
    spread_limits: dict[str, float] | None = None,
) -> SymbolReadiness:
    symbol = symbol.upper().replace("/", "")
    metadata = _catalog(catalog_path).get(symbol)
    result = SymbolReadiness(symbol=symbol, asset_class=(metadata or {}).get("asset_class", "unknown"))
    expected = month_range(start, end)
    if metadata is None:
        result.errors.append("symbol is not registered in config/symbols.yaml")

    result.raw_months, result.warnings = _raw_months(symbol, raw_root)
    result.missing_raw_months = sorted(set(expected) - set(result.raw_months))
    if result.missing_raw_months:
        result.errors.append("missing raw monthly coverage")

    candle_path = processed_root / symbol / "M1.parquet"
    if not candle_path.exists():
        result.missing_processed_months = expected
        result.errors.append("processed M1 parquet is missing")
        return result
    try:
        columns = set(pq.read_schema(candle_path).names)
        result.schema_valid = REQUIRED_CANDLE_COLUMNS.issubset(columns)
        if not result.schema_valid:
            result.errors.append("processed M1 schema is invalid")
            return result
        frame = pd.read_parquet(
            candle_path,
            columns=["timestamp_utc", "open", "high", "low", "close", "spread_avg"],
        )
    except Exception as exc:
        result.errors.append(f"processed M1 parquet is unreadable: {exc}")
        return result

    timestamps = pd.to_datetime(frame["timestamp_utc"], utc=True)
    in_window = (timestamps >= pd.Timestamp(start, tz="UTC")) & (
        timestamps < pd.Timestamp(end, tz="UTC") + pd.Timedelta(1, unit="D")
    )
    frame, timestamps = frame.loc[in_window].copy(), timestamps.loc[in_window]
    result.processed_months = sorted(timestamps.dt.strftime("%Y-%m").unique().tolist())
    result.missing_processed_months = sorted(set(expected) - set(result.processed_months))
    if result.missing_processed_months:
        result.errors.append("missing processed symbol-month coverage")

    result.ohlc_valid = bool(
        ((frame["high"] >= frame[["open", "close"]].max(axis=1)) &
         (frame["low"] <= frame[["open", "close"]].min(axis=1))).all()
    )
    if not result.ohlc_valid:
        result.errors.append("OHLC integrity failed")
    result.sorted = timestamps.is_monotonic_increasing
    if not result.sorted:
        result.errors.append("timestamps are not sorted")
    result.duplicates = int(timestamps.duplicated().sum())
    if result.duplicates:
        result.errors.append("duplicate timestamps found")

    if result.asset_class != "crypto":
        sunday_reopen = (timestamps.dt.dayofweek == 6) & (timestamps.dt.hour >= 20)
        invalid_weekend = (timestamps.dt.dayofweek == 5) | ((timestamps.dt.dayofweek == 6) & ~sunday_reopen)
        result.warnings["sunday_forex_reopen"] += int(sunday_reopen.sum())
        result.warnings["invalid_weekend_bars"] += int(invalid_weekend.sum())
    gaps = timestamps.diff().dropna()
    result.warnings["intraday_gaps"] += int(
        ((gaps > pd.Timedelta(2, unit="min")) & (gaps < pd.Timedelta(48, unit="h"))).sum()
    )
    limits = DEFAULT_SPREAD_LIMITS | (spread_limits or {})
    limit = limits.get(symbol)
    if limit is not None:
        result.warnings["large_spreads"] += int((frame["spread_avg"] > limit).sum())
    return result


def check_database(symbols: list[str], start: date, end: date, **kwargs: Any) -> dict[str, Any]:
    results = [check_symbol(symbol, start, end, **kwargs) for symbol in symbols]
    warning_counts = Counter()
    for result in results:
        warning_counts.update(result.warnings)
    blockers = sum(len(result.errors) for result in results)
    return {
        "status": "READY" if blockers == 0 else "NOT_READY",
        "start": start.isoformat(),
        "end": end.isoformat(),
        "symbols": [result.as_dict() for result in results],
        "warning_counts": dict(warning_counts),
        "blocking_error_count": blockers,
    }
