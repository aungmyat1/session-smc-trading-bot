#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from research.research_validation import run_dataset_research_audit


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Professional Dataset v2 research audit")
    parser.add_argument("--config", default="config/research_benchmark.yaml")
    parser.add_argument("--outdir", default="artifacts")
    args = parser.parse_args()

    result = run_dataset_research_audit(ROOT / args.config, ROOT / args.outdir)
    print(json.dumps({name: report["status"] for name, report in result.items()}, indent=2, sort_keys=True))
    return 0 if all(report["status"] == "PASS" for report in result.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
