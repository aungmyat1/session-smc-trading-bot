#!/usr/bin/env python3
"""
scripts/validate_dataset.py
Dataset Validation — Checks data quality for historical replay.
"""

from datetime import datetime
from pathlib import Path

import pandas as pd

PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD"]
TIMEFRAMES = ["M1", "M5", "M15", "H1", "H4", "D1"]

DATA_DIR = Path("data/processed")
REPORT_PATH = Path("reports/DATASET_VALIDATION_REPORT.md")


def validate_pair(pair: str) -> dict:
    """Validate all timeframes for a pair."""
    results = {"pair": pair, "timeframes": {}}

    for tf in TIMEFRAMES:
        file_path = DATA_DIR / pair / f"{pair}_{tf}.parquet"
        if not file_path.exists():
            results["timeframes"][tf] = {"status": "MISSING"}
            continue

        df = pd.read_parquet(file_path)

        results["timeframes"][tf] = {
            "status": "OK",
            "rows": len(df),
            "date_range": f"{df['timestamp'].min()} → {df['timestamp'].max()}",
            "nulls": df.isnull().sum().sum(),
            "avg_spread": (
                round(df["spread"].mean(), 5) if "spread" in df.columns else "N/A"
            ),
        }

    return results


def generate_report():
    """Generate validation report."""
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

    report = ["# DATASET VALIDATION REPORT", ""]
    report.append(f"Generated: {datetime.now().isoformat()}")
    report.append("")

    for pair in PAIRS:
        res = validate_pair(pair)
        report.append(f"## {pair}")
        for tf, data in res["timeframes"].items():
            if data["status"] == "MISSING":
                report.append(f"- **{tf}**: ❌ MISSING")
            else:
                report.append(
                    f"- **{tf}**: ✅ {data['rows']:,} bars | {data['date_range']} | Avg spread: {data['avg_spread']}"
                )
        report.append("")

    with open(REPORT_PATH, "w") as f:
        f.write("\n".join(report))

    print(f"✅ Validation report saved to {REPORT_PATH}")


if __name__ == "__main__":
    generate_report()
