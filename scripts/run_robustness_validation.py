#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from research.research_validation import robustness_report, write_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Run robustness validation from a trade ledger")
    parser.add_argument("--trades", help="CSV or JSON trade ledger from a pre-registered run")
    parser.add_argument("--out", default="artifacts/robustness_report.json")
    args = parser.parse_args()

    report = robustness_report(Path(args.trades) if args.trades else None)
    write_json(ROOT / args.out, report)
    print(json.dumps({"status": report["status"], "out": args.out}, indent=2, sort_keys=True))
    return 0 if report["status"] in {"PASS", "NOT_RUN"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
