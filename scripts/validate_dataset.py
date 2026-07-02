"""
Dataset validation script.

Checks raw tick Parquet and processed OHLCV Parquet for:
  - Month coverage gaps
  - Duplicate timestamps
  - OHLC integrity (high >= max(O,C), low <= min(O,C))
  - Spread anomalies (spread > threshold = flag)
  - Weekend bars
  - DST transition duplicates (2am–3am UTC)
  - Empty months

Writes: reports/dataset_validation_report.md

Usage:
    python scripts/validate_dataset.py
    python scripts/validate_dataset.py --symbols EURUSD --timeframes M15 H1 H4
"""

import argparse
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parent.parent
DATA_RAW  = ROOT / "data" / "raw" / "dukascopy"
DATA_PROC = ROOT / "data" / "processed"
DATA_MARKET = ROOT / "data" / "market"
REPORTS   = ROOT / "reports"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("validate")

SPREAD_WARN_PIPS = {
    "EURUSD": 10.0,
    "GBPUSD": 12.0,
    "USDJPY": 10.0,
    "XAUUSD": 5.0,
}
PIP_SIZE = {
    "EURUSD": 0.0001,
    "GBPUSD": 0.0001,
    "USDJPY": 0.01,
    "XAUUSD": 0.1,
}

EXPECTED_TF_GAPS = {
    "M1": timedelta(minutes=1),
    "M5": timedelta(minutes=5),
    "M15": timedelta(minutes=15),
    "H1": timedelta(hours=1),
    "H4": timedelta(hours=4),
    "D1": timedelta(days=1),
}

LEGACY_PROCESSED_COLS = [
    "timestamp_utc",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "ask_open",
    "bid_open",
    "spread_avg",
    "spread_max",
    "tick_count",
]

LAYERED_MARKET_COLS = [
    "timestamp_utc",
    "symbol",
    "timeframe",
    "open",
    "high",
    "low",
    "close",
    "tick_volume",
    "real_volume",
    "spread_mean",
    "spread_max",
]


def parse_year_month(value: str) -> tuple[int, int]:
    year, month = value.split("-")
    return int(year), int(month)


def month_range(start: tuple[int, int], end: tuple[int, int]):
    year, month = start
    while (year, month) <= end:
        yield year, month
        month += 1
        if month > 12:
            month = 1
            year += 1


def month_label(year_month: tuple[int, int]) -> str:
    year, month = year_month
    return f"{year}-{month:02d}"


def compute_month_coverage(
    months_found: list[tuple[int, int]],
    expected_start: tuple[int, int] | None = None,
    expected_end: tuple[int, int] | None = None,
) -> dict:
    if not months_found:
        return {
            "expected_months": [],
            "missing_months": [],
            "coverage": 0.0,
        }

    months_sorted = sorted(set(months_found))
    start = expected_start or months_sorted[0]
    end = expected_end or months_sorted[-1]
    expected_months = list(month_range(start, end))
    found = set(months_found)
    missing_months = [month for month in expected_months if month not in found]
    coverage = 0.0 if not expected_months else (len(expected_months) - len(missing_months)) / len(expected_months)
    return {
        "expected_months": expected_months,
        "missing_months": missing_months,
        "coverage": coverage,
    }


def load_acquisition_month_metadata(sym: str) -> list[dict]:
    sym_dir = DATA_RAW / sym
    if not sym_dir.exists():
        return []

    entries = []
    for year_dir in sorted(sym_dir.iterdir()):
        if not year_dir.is_dir():
            continue
        for month_dir in sorted(year_dir.iterdir()):
            if not month_dir.is_dir():
                continue
            meta_path = month_dir / "acquisition.json"
            if not meta_path.exists():
                continue
            try:
                entries.append(json.loads(meta_path.read_text()))
            except Exception as exc:
                entries.append(
                    {
                        "symbol": sym,
                        "month_key": f"{year_dir.name}-{month_dir.name}",
                        "status": "corrupt",
                        "error": str(exc),
                    }
                )
    return entries


class ValidationReport:
    def __init__(self):
        self.sections = []
        self.details = []
        self.errors = []
        self.warnings = []
        self.passed = []

    def add(self, level: str, msg: str):
        if level == "ERROR":
            self.errors.append(msg)
        elif level == "WARN":
            self.warnings.append(msg)
        else:
            self.passed.append(msg)
        self.sections.append((level, msg))

    def add_detail(self, markdown: str):
        self.details.append(markdown)

    def summary(self) -> str:
        lines = [
            "# Dataset Validation Report",
            f"Generated: {datetime.now(tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}",
            "",
            f"**ERRORS: {len(self.errors)} | WARNINGS: {len(self.warnings)} | PASSED: {len(self.passed)}**",
            "",
            "---",
            "",
            "## Checks",
            "",
        ]
        for level, msg in self.sections:
            icon = "🔴" if level == "ERROR" else "🟡" if level == "WARN" else "🟢"
            lines.append(f"{icon} [{level}] {msg}")

        if self.details:
            lines += ["", "---", "", "## Coverage Summary", ""]
            for block in self.details:
                lines.append(block)
                lines.append("")

        lines += ["", "---", "", "## Summary", ""]
        if not self.errors and not self.warnings:
            lines.append("✅ All checks passed. Dataset is clean.")
        elif not self.errors:
            lines.append(f"⚠️ {len(self.warnings)} warning(s). No blocking errors.")
        else:
            lines.append(f"❌ {len(self.errors)} error(s) found. Dataset needs remediation before use.")

        return "\n".join(lines)


def validate_raw_ticks(
    sym: str,
    report: ValidationReport,
    expected_start: tuple[int, int] | None = None,
    expected_end: tuple[int, int] | None = None,
):
    sym_dir = DATA_RAW / sym
    stats = {
        "symbol": sym,
        "raw_files": 0,
        "nonempty_months": [],
        "total_rows": 0,
        "coverage": 0.0,
        "missing_months": [],
    }
    if not sym_dir.exists():
        report.add("WARN", f"{sym}: no raw tick directory — download_dukascopy.py not yet run")
        return stats

    for year_dir in sorted(sym_dir.iterdir()):
        if not year_dir.is_dir():
            continue
        try:
            year = int(year_dir.name)
        except ValueError:
            continue
        for month_dir in sorted(year_dir.iterdir()):
            try:
                month = int(month_dir.name)
            except ValueError:
                continue
            tick_file = month_dir / "ticks.parquet"
            if not tick_file.exists():
                report.add("WARN", f"{sym}: missing tick file for {year}-{month:02d}")
                continue
            stats["raw_files"] += 1
            try:
                meta = pq.read_metadata(tick_file)
                n = meta.num_rows
            except Exception as e:
                report.add("ERROR", f"{sym}: corrupted Parquet {year}-{month:02d}: {e}")
                continue
            if n == 0:
                report.add("WARN", f"{sym}: zero ticks in {year}-{month:02d} (holiday month?)")
            else:
                stats["nonempty_months"].append((year, month))
                stats["total_rows"] += n
                report.add("PASS", f"{sym}: raw ticks {year}-{month:02d} — {n:,} rows OK")

    if stats["nonempty_months"]:
        # Check for month gaps
        prev = None
        for y, m in stats["nonempty_months"]:
            if prev:
                py, pm = prev
                expected_y, expected_m = (py, pm + 1) if pm < 12 else (py + 1, 1)
                if (y, m) != (expected_y, expected_m):
                    report.add("WARN", f"{sym}: month gap between {py}-{pm:02d} and {y}-{m:02d}")
            prev = (y, m)
        coverage = compute_month_coverage(stats["nonempty_months"], expected_start, expected_end)
        stats["coverage"] = coverage["coverage"]
        stats["missing_months"] = coverage["missing_months"]
        if stats["missing_months"]:
            preview = ", ".join(month_label(month) for month in stats["missing_months"][:6])
            if len(stats["missing_months"]) > 6:
                preview += ", ..."
            report.add(
                "WARN",
                f"{sym}: coverage {len(stats['nonempty_months'])}/{len(coverage['expected_months'])} months "
                f"({stats['coverage']:.1%}) — missing {preview}",
            )
        else:
            report.add(
                "PASS",
                f"{sym}: coverage {len(stats['nonempty_months'])}/{len(coverage['expected_months'])} months "
                f"({stats['coverage']:.1%})",
            )
    else:
        report.add("WARN", f"{sym}: no non-empty raw months found")

    return stats


def summarize_acquisition(sym: str) -> dict | None:
    entries = load_acquisition_month_metadata(sym)
    if not entries:
        return None

    good = [entry for entry in entries if entry.get("rows", 0) > 0]
    if not good:
        return {
            "months": len(entries),
            "rows": 0,
            "elapsed_seconds": 0.0,
            "rows_per_second": 0.0,
            "retries": 0,
            "hours_failed": 0,
            "hours_missing": 0,
            "hours_ok": 0,
        }

    elapsed_seconds = sum(float(entry.get("elapsed_seconds", 0.0)) for entry in good)
    total_rows = sum(int(entry.get("rows", 0)) for entry in good)
    total_retries = sum(int(entry.get("retries", 0)) for entry in good)
    hours_failed = sum(int(entry.get("hours_failed", 0)) for entry in good)
    hours_missing = sum(int(entry.get("hours_missing", 0)) for entry in good)
    hours_ok = sum(int(entry.get("hours_ok", 0)) for entry in good)
    return {
        "months": len(entries),
        "rows": total_rows,
        "elapsed_seconds": round(elapsed_seconds, 3),
        "rows_per_second": round(total_rows / elapsed_seconds, 2) if elapsed_seconds > 0 else 0.0,
        "retries": total_retries,
        "hours_failed": hours_failed,
        "hours_missing": hours_missing,
        "hours_ok": hours_ok,
    }


def validate_processed(sym: str, tf: str, report: ValidationReport):
    legacy_path = DATA_PROC / sym / f"{tf}.parquet"
    partition_root = DATA_MARKET / tf.lower() / sym
    partition_paths = sorted(partition_root.glob("year=*/month=*/part-*.parquet")) if partition_root.exists() else []
    path = legacy_path if legacy_path.exists() else (partition_paths[0] if partition_paths else legacy_path)
    stats = {
        "symbol": sym,
        "timeframe": tf,
        "exists": False,
        "rows": 0,
        "start": None,
        "end": None,
        "duplicates": 0,
        "schema_ok": False,
        "sorted": False,
        "storage": "legacy" if legacy_path.exists() else "partitioned" if partition_paths else "missing",
    }
    if not legacy_path.exists() and not partition_paths:
        report.add("WARN", f"{sym} {tf}: market dataset missing — run build_timeframes.py or research pipeline")
        return stats

    try:
        if legacy_path.exists():
            df = pd.read_parquet(legacy_path)
        else:
            df = pd.concat([pd.read_parquet(partition) for partition in partition_paths], ignore_index=True)
    except Exception as e:
        report.add("ERROR", f"{sym} {tf}: cannot read Parquet: {e}")
        return stats

    if df.empty:
        report.add("ERROR", f"{sym} {tf}: empty DataFrame")
        return stats

    n = len(df)
    stats["exists"] = True
    stats["rows"] = n
    report.add("PASS", f"{sym} {tf}: loaded {n:,} bars")

    # Ensure timestamp column
    ts_col = "timestamp_utc" if "timestamp_utc" in df.columns else df.columns[0]
    df[ts_col] = pd.to_datetime(df[ts_col], utc=True)
    schema_variants = [LEGACY_PROCESSED_COLS, LAYERED_MARKET_COLS]
    matched_schema = next((cols for cols in schema_variants if all(column in df.columns for column in cols)), None)
    if matched_schema is None:
        missing_cols = [
            [column for column in candidate if column not in df.columns]
            for candidate in schema_variants
        ]
        report.add("ERROR", f"{sym} {tf}: missing columns for supported schemas {missing_cols}")
    else:
        stats["schema_ok"] = True
        report.add("PASS", f"{sym} {tf}: schema complete")

    if df[ts_col].is_monotonic_increasing:
        stats["sorted"] = True
    else:
        report.add("ERROR", f"{sym} {tf}: timestamps not sorted")

    # Duplicate timestamps
    dups = df[ts_col].duplicated().sum()
    stats["duplicates"] = int(dups)
    if dups:
        report.add("ERROR", f"{sym} {tf}: {dups} duplicate timestamps")
    else:
        report.add("PASS", f"{sym} {tf}: no duplicate timestamps")

    # Weekend bars (Saturday=5, Sunday=6)
    weekend_timestamps = [timestamp for timestamp in df[ts_col] if timestamp.dayofweek >= 5]
    if weekend_timestamps:
        report.add("WARN", f"{sym} {tf}: {len(weekend_timestamps)} weekend bars found (first: {weekend_timestamps[0]})")
    else:
        report.add("PASS", f"{sym} {tf}: no weekend bars")

    # OHLC integrity
    if all(c in df.columns for c in ("open", "high", "low", "close")):
        bad_high = (df["high"] < df[["open", "close"]].max(axis=1)).sum()
        bad_low  = (df["low"]  > df[["open", "close"]].min(axis=1)).sum()
        if bad_high:
            report.add("ERROR", f"{sym} {tf}: {bad_high} bars where high < max(O,C)")
        else:
            report.add("PASS", f"{sym} {tf}: OHLC high integrity OK")
        if bad_low:
            report.add("ERROR", f"{sym} {tf}: {bad_low} bars where low > min(O,C)")
        else:
            report.add("PASS", f"{sym} {tf}: OHLC low integrity OK")

    # Spread anomalies
    spread_col = "spread_avg" if "spread_avg" in df.columns else "spread_mean" if "spread_mean" in df.columns else None
    if spread_col and sym in PIP_SIZE:
        spread_pips = df[spread_col] / PIP_SIZE[sym]
        threshold   = SPREAD_WARN_PIPS.get(sym, 10.0)
        anomalies   = (spread_pips > threshold).sum()
        if anomalies:
            report.add("WARN", f"{sym} {tf}: {anomalies} bars with spread > {threshold} pips")
        else:
            report.add("PASS", f"{sym} {tf}: spread within normal bounds")

    # Gap analysis (skip D1 — many gaps by design on weekends)
    if tf != "D1" and tf in EXPECTED_TF_GAPS:
        expected_gap = EXPECTED_TF_GAPS[tf]
        gaps = df[ts_col].diff().dropna()
        # Gaps > 2× expected that aren't at session boundaries or weekends
        large_gaps = gaps[gaps > expected_gap * 2]
        # Filter known weekend gaps (Friday close → Monday open: ~60h for H4, etc.)
        # A gap that starts on Friday (dayofweek=4) is expected
        if not large_gaps.empty:
            gap_starts = df.loc[large_gaps.index - 1, ts_col]
            non_weekend = gap_starts[gap_starts.dt.dayofweek < 4]
            if len(non_weekend) > 0:
                report.add("WARN", f"{sym} {tf}: {len(non_weekend)} non-weekend gaps > 2× bar size")
            else:
                report.add("PASS", f"{sym} {tf}: all large gaps are weekend closures (expected)")
        else:
            report.add("PASS", f"{sym} {tf}: no significant gaps")

    # Date range summary
    t0 = df[ts_col].iloc[0]
    t1 = df[ts_col].iloc[-1]
    stats["start"] = t0.isoformat()
    stats["end"] = t1.isoformat()
    report.add("PASS", f"{sym} {tf}: date range {t0.date()} → {t1.date()}")

    return stats


def main():
    parser = argparse.ArgumentParser(description="Validate historical data pipeline output")
    parser.add_argument("--symbols", nargs="+", default=["EURUSD", "GBPUSD"])
    parser.add_argument("--timeframes", nargs="+", default=["M1", "M5", "M15", "H1", "H4", "D1"])
    parser.add_argument("--expected-start", help="Expected start year-month e.g. 2023-07")
    parser.add_argument("--expected-end", help="Expected end year-month e.g. 2026-06")
    args = parser.parse_args()

    report = ValidationReport()
    expected_start = parse_year_month(args.expected_start) if args.expected_start else None
    expected_end = parse_year_month(args.expected_end) if args.expected_end else None
    raw_stats = {}
    processed_stats = {}

    for sym in args.symbols:
        raw_stats[sym] = validate_raw_ticks(sym, report, expected_start=expected_start, expected_end=expected_end)
        processed_stats[sym] = {}
        for tf in args.timeframes:
            processed_stats[sym][tf] = validate_processed(sym, tf, report)

    if expected_start and expected_end:
        report.add_detail(
            f"Expected raw coverage window: {month_label(expected_start)} → {month_label(expected_end)}"
        )

    raw_table = ["| Symbol | Raw files | Non-empty months | Coverage | Rows | Missing months |", "|---|---:|---:|---:|---:|---|"]
    for sym in args.symbols:
        stats = raw_stats[sym]
        missing = ", ".join(month_label(month) for month in stats["missing_months"]) if stats["missing_months"] else "None"
        raw_table.append(
            f"| {sym} | {stats['raw_files']} | {len(stats['nonempty_months'])} | {stats['coverage']:.1%} | "
            f"{stats['total_rows']:,} | {missing} |"
        )

    processed_table = ["| Symbol | TF | Rows | Schema | Sorted | Duplicates | Date range |", "|---|---|---:|---|---|---:|---|"]
    for sym in args.symbols:
        for tf in args.timeframes:
            stats = processed_stats[sym][tf]
            date_range = f"{stats['start'] or 'n/a'} → {stats['end'] or 'n/a'}"
            processed_table.append(
                f"| {sym} | {tf} | {stats['rows']:,} | {'PASS' if stats['schema_ok'] else 'FAIL'} | "
                f"{'PASS' if stats['sorted'] else 'FAIL'} | {stats['duplicates']} | {date_range} |"
            )

    acquisition_table = [
        "| Symbol | Months with telemetry | Rows | Elapsed sec | Rows/sec | Retries | Hours OK | Hours missing | Hours failed |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    acquisition_found = False
    for sym in args.symbols:
        summary = summarize_acquisition(sym)
        if summary is None:
            continue
        acquisition_found = True
        acquisition_table.append(
            f"| {sym} | {summary['months']} | {summary['rows']:,} | {summary['elapsed_seconds']:.3f} | "
            f"{summary['rows_per_second']:.2f} | {summary['retries']} | {summary['hours_ok']} | "
            f"{summary['hours_missing']} | {summary['hours_failed']} |"
        )

    report.add_detail("\n".join(["### Raw Coverage", "", *raw_table]))
    report.add_detail("\n".join(["### Processed Coverage", "", *processed_table]))
    if acquisition_found:
        report.add_detail("\n".join(["### Acquisition Telemetry", "", *acquisition_table]))

    REPORTS.mkdir(parents=True, exist_ok=True)
    out_path = REPORTS / "dataset_validation_report.md"
    out_path.write_text(report.summary())
    log.info("Report written to %s", out_path)

    print("\n" + report.summary())
    if report.errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
