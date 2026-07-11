#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from research.professional_dataset_v2.pipeline import ROOT, load_config, normalize_tick_file


def _discover_inputs(symbol: str, source: dict, raw_root: Path) -> list[Path]:
    if source["provider"] == "bitget_spot":
        return sorted((raw_root / "bitget" / symbol).glob("**/*.parquet"))
    return sorted((raw_root / "dukascopy" / symbol).glob("**/ticks.parquet"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize raw tick files into partitioned v2 tick parquet")
    parser.add_argument("--config", default="config/tick_dataset.yaml")
    parser.add_argument("--raw-root", default="data/raw")
    parser.add_argument("--output-root", default="data/tick")
    parser.add_argument("--symbol", action="append")
    args = parser.parse_args()

    config = load_config(ROOT / args.config)
    raw_root = ROOT / args.raw_root
    output_root = ROOT / args.output_root
    results = []
    for symbol in args.symbol or config["symbols"]:
        source = config["sources"][symbol]
        for input_path in _discover_inputs(symbol, source, raw_root):
            results.append(normalize_tick_file(input_path, output_root, symbol, source["asset_class"]))
    out = {"status": "PASS", "normalized": results}
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
