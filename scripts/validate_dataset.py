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
import logging
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parent.parent
DATA_RAW  = ROOT / "data" / "raw" / "dukascopy"
DATA_PROC = ROOT / "data" / "processed"
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
    "M1":  pd.Timedelta(minutes=1),
    "M5":  pd.Timedelta(minutes=5),
    "M15": pd.Timedelta(minutes=15),
    "H1":  pd.Timedelta(hours=1),
    "H4":  pd.Timedelta(hours=4),
    "D1":  pd.Timedelta(days=1),
}


class ValidationReport:
    def __init__(self):
        self.sections = []
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

        lines += ["", "---", "", "## Summary", ""]
        if not self.errors and not self.warnings:
            lines.append("✅ All checks passed. Dataset is clean.")
        elif not self.errors:
            lines.append(f"⚠️ {len(self.warnings)} warning(s). No blocking errors.")
        else:
            lines.append(f"❌ {len(self.errors)} error(s) found. Dataset needs remediation before use.")

        return "\n".join(lines)


def validate_raw_ticks(sym: str, report: ValidationReport):
    sym_dir = DATA_RAW / sym
    if not sym_dir.exists():
        report.add("WARN", f"{sym}: no raw tick directory — download_dukascopy.py not yet run")
        return

    months_found = []
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
            try:
                meta = pq.read_metadata(tick_file)
                n = meta.num_rows
            except Exception as e:
                report.add("ERROR", f"{sym}: corrupted Parquet {year}-{month:02d}: {e}")
                continue
            if n == 0:
                report.add("WARN", f"{sym}: zero ticks in {year}-{month:02d} (holiday month?)")
            else:
                months_found.append((year, month))
                report.add("PASS", f"{sym}: raw ticks {year}-{month:02d} — {n:,} rows OK")

    if months_found:
        # Check for month gaps
        prev = None
        for y, m in months_found:
            if prev:
                py, pm = prev
                expected_y, expected_m = (py, pm + 1) if pm < 12 else (py + 1, 1)
                if (y, m) != (expected_y, expected_m):
                    report.add("WARN", f"{sym}: month gap between {py}-{pm:02d} and {y}-{m:02d}")
            prev = (y, m)


def validate_processed(sym: str, tf: str, report: ValidationReport):
    path = DATA_PROC / sym / f"{tf}.parquet"
    if not path.exists():
        report.add("WARN", f"{sym} {tf}: processed file missing — run build_timeframes.py")
        return

    try:
        df = pd.read_parquet(path)
    except Exception as e:
        report.add("ERROR", f"{sym} {tf}: cannot read Parquet: {e}")
        return

    if df.empty:
        report.add("ERROR", f"{sym} {tf}: empty DataFrame")
        return

    n = len(df)
    report.add("PASS", f"{sym} {tf}: loaded {n:,} bars")

    # Ensure timestamp column
    ts_col = "timestamp_utc" if "timestamp_utc" in df.columns else df.columns[0]
    df[ts_col] = pd.to_datetime(df[ts_col], utc=True)
    df = df.sort_values(ts_col).reset_index(drop=True)

    # Duplicate timestamps
    dups = df[ts_col].duplicated().sum()
    if dups:
        report.add("ERROR", f"{sym} {tf}: {dups} duplicate timestamps")
    else:
        report.add("PASS", f"{sym} {tf}: no duplicate timestamps")

    # Weekend bars (Saturday=5, Sunday=6)
    weekends = df[df[ts_col].dt.dayofweek >= 5]
    if not weekends.empty:
        report.add("WARN", f"{sym} {tf}: {len(weekends)} weekend bars found (first: {weekends[ts_col].iloc[0]})")
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
    if "spread_avg" in df.columns and sym in PIP_SIZE:
        spread_pips = df["spread_avg"] / PIP_SIZE[sym]
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
    report.add("PASS", f"{sym} {tf}: date range {t0.date()} → {t1.date()}")


def main():
    parser = argparse.ArgumentParser(description="Validate historical data pipeline output")
    parser.add_argument("--symbols", nargs="+", default=["EURUSD", "GBPUSD"])
    parser.add_argument("--timeframes", nargs="+", default=["M1", "M5", "M15", "H1", "H4", "D1"])
    args = parser.parse_args()

    report = ValidationReport()

    for sym in args.symbols:
        validate_raw_ticks(sym, report)
        for tf in args.timeframes:
            validate_processed(sym, tf, report)

    REPORTS.mkdir(parents=True, exist_ok=True)
    out_path = REPORTS / "dataset_validation_report.md"
    out_path.write_text(report.summary())
    log.info("Report written to %s", out_path)

    print("\n" + report.summary())
    if report.errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
