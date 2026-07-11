#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from research.professional_dataset_v2.pipeline import ROOT, QualityThresholds, dataset_quality, load_config


def main() -> int:
    parser = argparse.ArgumentParser(description="Run professional dataset v2 quality gates")
    parser.add_argument("--config", default="config/tick_dataset.yaml")
    parser.add_argument("--processed-root", default=None)
    parser.add_argument("--output", default="artifacts/data_quality_report.json")
    args = parser.parse_args()
    config = load_config(ROOT / args.config)
    thresholds = config.get("quality_thresholds", {})
    report = dataset_quality(
        ROOT / (args.processed_root or config.get("processed_root", "data/processed")),
        ROOT / args.output,
        QualityThresholds(**thresholds),
    )
    print(f"Wrote {ROOT / args.output}")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
