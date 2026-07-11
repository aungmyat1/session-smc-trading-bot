#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from research.professional_dataset_v2.pipeline import ROOT, cost_model_validation


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate professional dataset v2 cost models")
    parser.add_argument("--cost-root", default="research/cost_models")
    parser.add_argument("--output", default="artifacts/cost_model_validation_report.json")
    args = parser.parse_args()
    report = cost_model_validation(ROOT / args.cost_root)
    out = ROOT / args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"status": report["status"]}, indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

