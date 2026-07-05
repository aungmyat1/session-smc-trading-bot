#!/usr/bin/env python3
"""CLI readiness gate for canonical System 1 research data."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research_db.readiness import check_database  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbols", nargs="+", required=True)
    parser.add_argument("--start", type=date.fromisoformat, required=True)
    parser.add_argument("--end", type=date.fromisoformat, required=True)
    parser.add_argument("--spread-limit", action="append", default=[], metavar="SYMBOL=PRICE")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    spread_limits = {}
    for item in args.spread_limit:
        symbol, value = item.split("=", 1)
        spread_limits[symbol.upper().replace("/", "")] = float(value)
    report = check_database(args.symbols, args.start, args.end, spread_limits=spread_limits)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(report["status"])
        for item in report["symbols"]:
            print(
                f"{item['symbol']}: raw={len(item['raw_months'])} months "
                f"processed={len(item['processed_months'])} months "
                f"missing_raw={item['missing_raw_months'] or 'none'} "
                f"missing_processed={item['missing_processed_months'] or 'none'} "
                f"schema={item['schema_valid']} ohlc={item['ohlc_valid']} "
                f"sorted={item['sorted']} duplicates={item['duplicates']}"
            )
        print(f"warnings={report['warning_counts']}")
        print(f"blocking_errors={report['blocking_error_count']}")
    return 0 if report["status"] == "READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
