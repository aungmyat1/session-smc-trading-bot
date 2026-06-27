"""
Normalize Dukascopy raw tick Parquet into a unified tick schema and layout.

This script is memory-safe for multi-year datasets: it streams each monthly raw
file into a symbol-level Parquet writer instead of loading the full symbol into
RAM.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parent.parent
RAW_ROOT = ROOT / "data" / "raw" / "dukascopy"
NORM_ROOT = ROOT / "data" / "normalized"
MARKET_ROOT = ROOT / "data" / "market"

TICK_SCHEMA = pa.schema(
    [
        ("timestamp_utc", pa.timestamp("ns", tz="UTC")),
        ("bid", pa.float32()),
        ("ask", pa.float32()),
        ("spread", pa.float32()),
        ("ask_vol", pa.float32()),
        ("bid_vol", pa.float32()),
    ]
)

DATASET_TREE = [
    NORM_ROOT / "tick" / "EURUSD",
    NORM_ROOT / "tick" / "GBPUSD",
    NORM_ROOT / "tick" / "USDJPY",
    NORM_ROOT / "tick" / "XAUUSD",
    NORM_ROOT / "metadata",
    MARKET_ROOT / "m1",
    MARKET_ROOT / "m5",
    MARKET_ROOT / "m15",
    MARKET_ROOT / "m30",
    MARKET_ROOT / "h1",
    MARKET_ROOT / "h4",
    MARKET_ROOT / "d1",
    MARKET_ROOT / "w1",
    ROOT / "data" / "sessions" / "london",
    ROOT / "data" / "sessions" / "new_york",
    ROOT / "data" / "sessions" / "asian",
    ROOT / "data" / "sessions" / "overlap",
    ROOT / "data" / "structure" / "swings",
    ROOT / "data" / "structure" / "trend",
    ROOT / "data" / "structure" / "bos",
    ROOT / "data" / "structure" / "choch",
    ROOT / "data" / "structure" / "internal_structure",
    ROOT / "data" / "structure" / "external_structure",
    ROOT / "data" / "liquidity" / "equal_highs",
    ROOT / "data" / "liquidity" / "equal_lows",
    ROOT / "data" / "liquidity" / "liquidity_sweeps",
    ROOT / "data" / "liquidity" / "stop_hunts",
    ROOT / "data" / "liquidity" / "inducements",
    ROOT / "data" / "imbalances" / "fvg",
    ROOT / "data" / "imbalances" / "inverse_fvg",
    ROOT / "data" / "imbalances" / "gaps",
    ROOT / "data" / "imbalances" / "imbalance_clusters",
    ROOT / "data" / "orderflow" / "order_blocks",
    ROOT / "data" / "orderflow" / "breaker_blocks",
    ROOT / "data" / "orderflow" / "mitigation_blocks",
    ROOT / "data" / "orderflow" / "rejection_blocks",
    ROOT / "data" / "confluence" / "premium_discount",
    ROOT / "data" / "confluence" / "fib_levels",
    ROOT / "data" / "confluence" / "daily_bias",
    ROOT / "data" / "confluence" / "weekly_bias",
    ROOT / "data" / "confluence" / "higher_timeframe_context",
]


def ensure_layout() -> None:
    for path in DATASET_TREE:
        path.mkdir(parents=True, exist_ok=True)


def discover_symbols() -> list[str]:
    if not RAW_ROOT.exists():
        return []
    return sorted([p.name for p in RAW_ROOT.iterdir() if p.is_dir()])


def iter_month_files(symbol: str):
    base = RAW_ROOT / symbol
    for tick_file in sorted(base.glob("*/*/ticks.parquet")):
        yield tick_file


def normalize_frame(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "timestamp_utc" not in out.columns:
        out["timestamp_utc"] = pd.to_datetime(out["timestamp_ms"], unit="ms", utc=True)
    else:
        out["timestamp_utc"] = pd.to_datetime(out["timestamp_utc"], utc=True)

    out = out.sort_values("timestamp_utc").reset_index(drop=True)
    out["bid"] = out["bid"].astype("float32")
    out["ask"] = out["ask"].astype("float32")
    out["spread"] = (out["ask"] - out["bid"]).astype("float32")
    if "ask_vol" not in out.columns:
        out["ask_vol"] = 0.0
    if "bid_vol" not in out.columns:
        out["bid_vol"] = 0.0
    out["ask_vol"] = out["ask_vol"].astype("float32")
    out["bid_vol"] = out["bid_vol"].astype("float32")
    return out[["timestamp_utc", "bid", "ask", "spread", "ask_vol", "bid_vol"]]


def write_symbol(symbol: str) -> dict:
    out_dir = NORM_ROOT / "tick" / symbol
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "ticks.parquet"

    writer: pq.ParquetWriter | None = None
    stats = {
        "symbol": symbol,
        "path": str(out_path.relative_to(ROOT)),
        "rows": 0,
        "first_timestamp": None,
        "last_timestamp": None,
        "file_size_bytes": 0,
        "average_spread": None,
        "min_spread": None,
        "max_spread": None,
    }
    spread_sum = 0.0
    spread_min = None
    spread_max = None

    for tick_file in iter_month_files(symbol):
        df = pd.read_parquet(tick_file)
        if df.empty:
            continue
        normalized = normalize_frame(df)
        table = pa.Table.from_pandas(normalized, schema=TICK_SCHEMA, preserve_index=False)
        if writer is None:
            writer = pq.ParquetWriter(out_path, TICK_SCHEMA, compression="snappy")
        writer.write_table(table)

        stats["rows"] += int(len(normalized))
        if stats["first_timestamp"] is None:
            stats["first_timestamp"] = normalized["timestamp_utc"].iloc[0].isoformat()
        stats["last_timestamp"] = normalized["timestamp_utc"].iloc[-1].isoformat()

        spreads = normalized["spread"]
        spread_sum += float(spreads.sum())
        mn = float(spreads.min())
        mx = float(spreads.max())
        spread_min = mn if spread_min is None else min(spread_min, mn)
        spread_max = mx if spread_max is None else max(spread_max, mx)

    if writer is not None:
        writer.close()
        stats["file_size_bytes"] = out_path.stat().st_size
        if stats["rows"] > 0:
            stats["average_spread"] = spread_sum / stats["rows"]
            stats["min_spread"] = spread_min
            stats["max_spread"] = spread_max

    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize Dukascopy ticks into a unified schema")
    parser.add_argument("--symbols", nargs="+", help="Symbols to process; defaults to all raw symbols")
    args = parser.parse_args()

    ensure_layout()
    symbols = args.symbols or discover_symbols()

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_root": str(RAW_ROOT.relative_to(ROOT)),
        "normalized_root": str(NORM_ROOT.relative_to(ROOT)),
        "symbols": [],
    }

    for symbol in symbols:
        if not any(iter_month_files(symbol)):
            continue
        manifest["symbols"].append(write_symbol(symbol))

    meta_path = NORM_ROOT / "metadata" / "dataset_manifest.json"
    meta_path.write_text(json.dumps(manifest, indent=2))
    print(f"Wrote manifest: {meta_path}")


if __name__ == "__main__":
    main()
