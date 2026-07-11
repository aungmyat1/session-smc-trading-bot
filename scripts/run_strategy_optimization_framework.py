#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from research.optimization_runner import run_framework


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the failure-driven SVOS optimization framework")
    parser.add_argument("--strategy", default="ST-A2")
    parser.add_argument("--validation-report", default="artifacts/ST-A2_validation_report.json")
    parser.add_argument("--candidate-report", help="Optional candidate validation report JSON")
    parser.add_argument("--candidate-trades", help="Optional candidate trade ledger CSV/JSON")
    args = parser.parse_args()

    result = run_framework(
        strategy=args.strategy,
        validation_report_path=ROOT / args.validation_report,
        candidate_report_path=(ROOT / args.candidate_report) if args.candidate_report else None,
        candidate_trades_path=(ROOT / args.candidate_trades) if args.candidate_trades else None,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
