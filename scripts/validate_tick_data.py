#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from research.professional_dataset_v2.pipeline import ROOT, load_config, validate_tick_partitions


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate professional dataset v2 tick partitions")
    parser.add_argument("--config", default="config/tick_dataset.yaml")
    parser.add_argument("--tick-root", default="data/tick")
    parser.add_argument("--output", default="artifacts/tick_validation_report.json")
    args = parser.parse_args()

    config = load_config(ROOT / args.config)
    report = validate_tick_partitions(ROOT / args.tick_root, config["symbols"])
    out = ROOT / args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(f"Wrote {out}")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
