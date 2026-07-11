#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from research.professional_dataset_v2.pipeline import ROOT, load_config, validate_dataset_completeness


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate professional dataset v2 tick completeness")
    parser.add_argument("--config", default="config/tick_dataset.yaml")
    parser.add_argument("--tick-root", default="data/tick")
    args = parser.parse_args()
    report = validate_dataset_completeness(load_config(ROOT / args.config), ROOT / args.tick_root)
    print(json.dumps({"status": report["status"], "completion_pct": report["completion_pct"], "missing_partitions": report["missing_partitions"]}, indent=2, sort_keys=True))
    return 0 if report["status"] != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
