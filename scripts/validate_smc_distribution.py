#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from research.professional_dataset_v2.pipeline import ROOT, smc_distribution_validation


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate professional dataset v2 SMC distributions")
    parser.add_argument("--smc-root", default="research/smc_events")
    parser.add_argument("--output", default="artifacts/smc_distribution_report.json")
    args = parser.parse_args()
    report = smc_distribution_validation(ROOT / args.smc_root)
    out = ROOT / args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"status": report["status"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

