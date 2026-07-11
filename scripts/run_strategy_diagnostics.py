#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from research.strategy_diagnostics import run_diagnostics


def main() -> int:
    parser = argparse.ArgumentParser(description="Classify strategy validation failures")
    parser.add_argument("--input", default="artifacts/ST-A2_validation_report.json")
    parser.add_argument("--out", default="artifacts/strategy_failure_diagnosis.json")
    parser.add_argument("--benchmark", default="config/research_benchmark.yaml")
    args = parser.parse_args()

    result = run_diagnostics(ROOT / args.input, ROOT / args.out, ROOT / args.benchmark)
    print(
        json.dumps(
            {
                "out": args.out,
                "strategy": result["strategy"],
                "detected_failures": len(result["detected_failures"]),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
