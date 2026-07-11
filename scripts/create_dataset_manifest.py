#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from research.professional_dataset_v2.pipeline import ROOT, create_manifest, load_config


def main() -> int:
    parser = argparse.ArgumentParser(description="Create immutable dataset v2 manifest")
    parser.add_argument("--config", default="config/tick_dataset.yaml")
    parser.add_argument("--dataset-dir", default="datasets/professional_3y_4symbol_v2")
    parser.add_argument("--quality-report", default="artifacts/data_quality_report.json")
    args = parser.parse_args()
    manifest = create_manifest(load_config(ROOT / args.config), ROOT / args.dataset_dir, ROOT / args.quality_report)
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
