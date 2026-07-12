#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from research.professional_dataset_v2.pipeline import ROOT, release_validation_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the professional dataset v2 release gate")
    parser.add_argument("--dataset-dir", default="datasets/professional_3y_4symbol_v2")
    parser.add_argument("--output", default="artifacts/release_validation_report.json")
    args = parser.parse_args()
    report = release_validation_report(ROOT / args.dataset_dir)
    out = ROOT / args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"release_status": report["release_status"], "completion_pct": report["completion_pct"]}, indent=2, sort_keys=True))
    return 0 if report["release_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
