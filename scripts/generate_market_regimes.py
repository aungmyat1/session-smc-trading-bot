#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from research.professional_dataset_v2.pipeline import ROOT, generate_market_regimes, load_config


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate professional dataset v2 market regime labels")
    parser.add_argument("--config", default="config/tick_dataset.yaml")
    parser.add_argument("--processed-root", default=None)
    parser.add_argument("--output-root", default="research/market_regimes")
    parser.add_argument("--timeframe", default="M15")
    args = parser.parse_args()
    config = load_config(ROOT / args.config)
    summary = generate_market_regimes(
        ROOT / (args.processed_root or config.get("processed_root", "data/processed")),
        ROOT / args.output_root,
        config["symbols"],
        args.timeframe,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
