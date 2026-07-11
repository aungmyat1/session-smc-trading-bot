#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from research.research_validation import write_strategy_audit_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect SVOS strategy audit inventory")
    parser.add_argument("--out", default="artifacts/strategy_audit_report.json")
    args = parser.parse_args()

    report = write_strategy_audit_report(ROOT / args.out)
    print(json.dumps({"strategies": len(report["strategies"]), "out": args.out}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
