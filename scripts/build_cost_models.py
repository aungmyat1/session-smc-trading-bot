#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from research.professional_dataset_v2.pipeline import ROOT, build_cost_models, load_config


def main() -> int:
    parser = argparse.ArgumentParser(description="Build spread, commission, and slippage cost models")
    parser.add_argument("--config", default="config/tick_dataset.yaml")
    parser.add_argument("--tick-root", default="data/tick")
    parser.add_argument("--output-root", default="research/cost_models")
    args = parser.parse_args()
    config = load_config(ROOT / args.config)
    summary = build_cost_models(
        ROOT / args.tick_root,
        ROOT / args.output_root,
        config["symbols"],
        ROOT / config.get("processed_root", "data/processed"),
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
