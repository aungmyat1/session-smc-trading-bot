#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from research.professional_dataset_v2.pipeline import ROOT, load_config, refresh_plan


def main() -> int:
    parser = argparse.ArgumentParser(description="Plan incremental professional dataset v2 refreshes")
    parser.add_argument("--config", default="config/tick_dataset.yaml")
    parser.add_argument("--tick-root", default="data/tick")
    parser.add_argument("--checksums", default="datasets/professional_3y_4symbol_v2/checksums.json")
    parser.add_argument("--output", default="artifacts/dataset_refresh_plan.json")
    args = parser.parse_args()
    plan = refresh_plan(load_config(ROOT / args.config), ROOT / args.tick_root, ROOT / args.checksums)
    out = ROOT / args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(plan, indent=2, sort_keys=True), encoding="utf-8")
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
