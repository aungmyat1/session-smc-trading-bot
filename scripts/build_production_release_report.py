#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from research.professional_dataset_v2.pipeline import ROOT, production_release_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the production release report")
    parser.add_argument("--dataset-dir", default="datasets/professional_3y_4symbol_v2")
    parser.add_argument("--output", default="artifacts/production_release_report.json")
    args = parser.parse_args()
    report = production_release_report(ROOT / args.dataset_dir)
    out = ROOT / args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
