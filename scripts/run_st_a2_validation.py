#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from research.research_validation import st_a2_validation_report, write_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate ST-A2 validation metrics from an immutable trade ledger")
    parser.add_argument("--trades", help="CSV, JSON, Parquet, or ledger directory from a pre-registered run")
    parser.add_argument("--out", default="artifacts/ST-A2_validation_report.json")
    args = parser.parse_args()

    default_ledger = ROOT / "research" / "trade_ledgers"
    trades_path = Path(args.trades) if args.trades else (default_ledger if default_ledger.exists() else None)
    report = st_a2_validation_report(trades_path)
    write_json(ROOT / args.out, report)
    print(json.dumps({"status": report["status"], "out": args.out}, indent=2, sort_keys=True))
    return 0 if report["status"] in {"PASS", "FAIL", "INSUFFICIENT_DATA", "BLOCKED"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
