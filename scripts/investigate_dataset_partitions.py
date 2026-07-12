#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from research.professional_dataset_v2.pipeline import ROOT, investigate_partitions, load_config


def main() -> int:
    parser = argparse.ArgumentParser(description="Investigate unresolved professional dataset v2 partitions")
    parser.add_argument("--config", default="config/tick_dataset.yaml")
    parser.add_argument("--tick-root", default="data/tick")
    parser.add_argument("--refresh-plan", default="artifacts/dataset_refresh_plan.json")
    args = parser.parse_args()
    report = investigate_partitions(load_config(ROOT / args.config), ROOT / args.tick_root, ROOT / args.refresh_plan)
    print(json.dumps({"total_actions": report["total_actions"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
