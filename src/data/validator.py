from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd


@dataclass
class ValidationReport:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    stats: dict[str, int] = field(default_factory=dict)


def validate_candles(
    frame: pd.DataFrame, expected_freq: str = "1min"
) -> ValidationReport:
    """Validate timezone, OHLC integrity, duplicate timestamps, and gaps."""
    errors: list[str] = []
    warnings: list[str] = []
    stats: dict[str, int] = {}

    if frame.empty:
        return ValidationReport(False, ["empty frame"], [], {"rows": 0})

    df = frame.copy()
    ts = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    if ts.isna().any():
        errors.append("unparseable timestamps")
    if getattr(ts.dt, "tz", None) is None:
        errors.append("timestamps are not timezone-aware")

    dup_count = int(ts.duplicated().sum())
    if dup_count:
        errors.append(f"duplicate timestamps: {dup_count}")

    bad_ohlc = ~(
        (df["high"] >= df[["open", "close"]].max(axis=1))
        & (df["low"] <= df[["open", "close"]].min(axis=1))
        & (df["high"] >= df["low"])
    )
    bad_count = int(bad_ohlc.sum())
    if bad_count:
        errors.append(f"invalid OHLC rows: {bad_count}")

    ts_sorted = ts.sort_values().reset_index(drop=True)
    diffs = ts_sorted.diff().dropna()
    expected_delta = pd.Timedelta(expected_freq)
    gaps = diffs[diffs > expected_delta]
    gap_count = int(gaps.count())
    stats["gap_count"] = gap_count
    missing = 0
    weekend = 0
    if gap_count:
        for idx, delta in gaps.items():
            prev_ts = ts_sorted.iloc[idx - 1]
            curr_ts = ts_sorted.iloc[idx]
            missing += max(int(delta / expected_delta) - 1, 0)
            if prev_ts.weekday() == 4 and curr_ts.weekday() == 0:
                weekend += 1
        if missing:
            stats["missing_candles"] = missing
        if weekend:
            warnings.append(f"weekend gaps observed: {weekend}")
        warnings.append(
            f"gaps observed: {gap_count} ({missing} missing candles vs {expected_freq} cadence)"
        )

    stats["rows"] = int(len(df))
    stats["duplicates"] = dup_count
    stats["invalid_ohlc"] = bad_count
    return ValidationReport(
        ok=not errors, errors=errors, warnings=warnings, stats=stats
    )
