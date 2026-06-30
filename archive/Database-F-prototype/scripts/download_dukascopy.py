#!/usr/bin/env python3
"""
scripts/download_dukascopy.py
Professional Dukascopy Tick Data Downloader (v2)

Downloads tick-level data (bid/ask) and converts to Parquet.

Usage examples:
    python scripts/download_dukascopy.py --pair EURUSD --start 2024-01-01 --end 2024-12-31
    python scripts/download_dukascopy.py --all
"""

import argparse
import subprocess
from datetime import datetime
from pathlib import Path
import pandas as pd
import shutil

OUTPUT_DIR = Path("data/raw_ticks")
PROCESSED_DIR = Path("data/processed")


def check_dukascopy_node():
    """Check if dukascopy-node is available."""
    if shutil.which("npx") is None:
        print("❌ Node.js / npx not found. Please install Node.js first.")
        return False
    try:
        subprocess.run(
            ["npx", "dukascopy-node", "--version"], capture_output=True, check=True
        )
        return True
    except:
        print("Installing dukascopy-node...")
        subprocess.run(["npm", "install", "-g", "dukascopy-node"], check=True)
        return True


def download_pair(pair: str, start: str, end: str):
    """Download tick data using dukascopy-node."""
    if not check_dukascopy_node():
        return False

    output_path = OUTPUT_DIR / pair
    output_path.mkdir(parents=True, exist_ok=True)

    cmd = [
        "npx",
        "dukascopy-node",
        "-i",
        pair,
        "-from",
        start,
        "-to",
        end,
        "-t",
        "tick",
        "-f",
        "csv",
        "-folder",
        str(output_path),
    ]

    print(f"Downloading {pair} tick data ({start} → {end})...")
    try:
        subprocess.run(cmd, check=True)
        print(f"  ✅ {pair} downloaded")
        return True
    except subprocess.CalledProcessError as e:
        print(f"  ❌ Failed to download {pair}: {e}")
        return False


def convert_to_parquet(pair: str):
    """Convert downloaded CSV files to one compressed Parquet file."""
    csv_dir = OUTPUT_DIR / pair
    parquet_dir = PROCESSED_DIR / pair
    parquet_dir.mkdir(parents=True, exist_ok=True)

    csv_files = sorted(csv_dir.glob("*.csv"))
    if not csv_files:
        print(f"  No CSV files found for {pair}")
        return

    print(f"Converting {pair} to Parquet...")
    dfs = []
    for csv_file in csv_files:
        try:
            df = pd.read_csv(csv_file, parse_dates=["timestamp"])
            dfs.append(df)
        except Exception as e:
            print(f"  Warning: Could not read {csv_file}: {e}")

    if dfs:
        full_df = pd.concat(dfs, ignore_index=True)
        full_df = full_df.sort_values("timestamp")
        full_df["spread"] = full_df["ask"] - full_df["bid"]

        output_file = parquet_dir / f"{pair}_TICK.parquet"
        full_df.to_parquet(output_file, compression="zstd", index=False)
        print(f"  ✅ Saved {len(full_df):,} ticks → {output_file}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pair", help="Trading pair (e.g. EURUSD)")
    parser.add_argument("--start", default="2024-01-01")
    parser.add_argument("--end", default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--all", action="store_true", help="Download all major pairs")
    args = parser.parse_args()

    print("=" * 60)
    print("Dukascopy Tick Data Downloader v2")
    print("=" * 60)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    pairs = ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD"] if args.all else [args.pair]

    for pair in pairs:
        if pair is None:
            continue
        success = download_pair(pair, args.start, args.end)
        if success:
            convert_to_parquet(pair)

    print("\n✅ Dukascopy download pipeline complete.")


if __name__ == "__main__":
    main()
