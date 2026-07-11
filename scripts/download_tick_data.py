#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from research.professional_dataset_v2.pipeline import ROOT, load_config


def main() -> int:
    parser = argparse.ArgumentParser(description="Download raw tick/candle inputs for professional dataset v2")
    parser.add_argument("--config", default="config/tick_dataset.yaml")
    parser.add_argument("--symbol", action="append", help="Limit to one or more symbols")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()

    config = load_config(ROOT / args.config)
    symbols = args.symbol or config["symbols"]
    commands: list[list[str]] = []
    for symbol in symbols:
        source = config["sources"][symbol]
        if source["provider"] == "bitget_spot":
            commands.append(
                [
                    sys.executable,
                    "scripts/download_bitget_candles.py",
                    "--symbol",
                    symbol,
                    "--source-symbol",
                    "BTCUSDT",
                    "--start",
                    config["window"]["start"],
                    "--end",
                    config["window"]["end"],
                ]
            )
        elif source["provider"] == "dukascopy":
            commands.append(
                [
                    sys.executable,
                    "scripts/download_dukascopy.py",
                    "--symbols",
                    symbol,
                    "--start",
                    config["window"]["start"],
                    "--end",
                    config["window"]["end"],
                    "--workers",
                    str(args.workers),
                ]
            )
    for command in commands:
        print("+ " + " ".join(command))
        if not args.dry_run:
            subprocess.run(command, cwd=ROOT, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
