#!/usr/bin/env python3
"""
Stage 2 — Feature Generation Layer (SMC)
Generates all Smart Money Concepts features from raw M1 data.
"""

from pathlib import Path
from datetime import time, datetime, timedelta

import polars as pl

RAW_DIR = Path("data/raw")
FEATURES_DIR = Path("features")
FEATURES_DIR.mkdir(exist_ok=True)

SYMBOLS = ["EURUSD", "GBPUSD", "XAUUSD"]

# ==================== 2.1 SESSION LABELS ====================
def add_session_labels(df: pl.DataFrame) -> pl.DataFrame:
    """Add session columns (London & New York)."""
    df = df.with_columns([
        pl.col("time").dt.time().alias("t"),
    ])

    london_mask = (pl.col("t") >= time(8, 0)) & (pl.col("t") < time(16, 0))
    ny_mask = (pl.col("t") >= time(13, 0)) & (pl.col("t") < time(21, 0))

    df = df.with_columns([
        pl.when(london_mask).then(pl.lit("London")).otherwise(pl.lit(None)).alias("session_london"),
        pl.when(ny_mask).then(pl.lit("NewYork")).otherwise(pl.lit(None)).alias("session_ny"),
    ]).drop("t")

    return df

def save_session_labels(symbol: str, df: pl.DataFrame):
    out_path = FEATURES_DIR / "session_labels.parquet"
    session_df = df.select(["time", "session_london", "session_ny"])
    session_df.write_parquet(out_path, compression="zstd")
    print(f"  Saved session labels → {out_path}")

# ==================== 2.2 SWING DETECTION ====================
def detect_swings(df: pl.DataFrame) -> pl.DataFrame:
    """Simple 3-bar swing detection."""
    df = df.with_columns([
        ((pl.col("high") > pl.col("high").shift(1)) &
         (pl.col("high") > pl.col("high").shift(-1))).alias("is_swing_high"),

        ((pl.col("low") < pl.col("low").shift(1)) &
         (pl.col("low") < pl.col("low").shift(-1))).alias("is_swing_low")
    ])

    swings = []
    for row in df.iter_rows(named=True):
        if row["is_swing_high"]:
            swings.append({
                "time": row["time"],
                "swing_type": "high",
                "t1": row["time"],
                "high": row["high"],
            })
        if row["is_swing_low"]:
            swings.append({
                "time": row["time"],
                "swing_type": "low",
                "t1": row["time"],
                "low": row["low"],
            })

    if not swings:
        return pl.DataFrame(schema={"time": pl.Datetime, "swing_type": pl.Utf8, "t1": pl.Datetime, "high": pl.Float64, "low": pl.Float64})

    swing_df = pl.DataFrame(swings)
    return swing_df

def save_swings(symbol: str, swing_df: pl.DataFrame):
    out_path = FEATURES_DIR / "swings.parquet"
    swing_df.write_parquet(out_path, compression="zstd")
    print(f"  Saved swings → {out_path} ({len(swing_df)} swings)")

# ==================== 2.3 MARKET STRUCTURE ====================
def detect_market_structure(df: pl.DataFrame, swings: pl.DataFrame) -> pl.DataFrame:
    """Very basic BOS / CHOCH detection based on swing sequence."""
    if swings.is_empty():
        return pl.DataFrame(schema={"time": pl.Datetime, "structure": pl.Utf8, "t1": pl.Datetime})

    # Sort swings chronologically
    swings = swings.sort("time")

    structures = []
    prev_type = None
    prev_price = None

    for row in swings.iter_rows(named=True):
        if row["swing_type"] == "high":
            price = row["high"]
            if prev_type == "high" and price > prev_price:
                structures.append({"time": row["time"], "structure": "HH", "t1": row["time"]})
            elif prev_type == "low" and price > prev_price:
                structures.append({"time": row["time"], "structure": "BOS_BULL", "t1": row["time"]})
            prev_type = "high"
            prev_price = price
        else:  # low
            price = row["low"]
            if prev_type == "low" and price < prev_price:
                structures.append({"time": row["time"], "structure": "LL", "t1": row["time"]})
            elif prev_type == "high" and price < prev_price:
                structures.append({"time": row["time"], "structure": "BOS_BEAR", "t1": row["time"]})
            prev_type = "low"
            prev_price = price

    if not structures:
        return pl.DataFrame(schema={"time": pl.Datetime, "structure": pl.Utf8, "t1": pl.Datetime})

    return pl.DataFrame(structures)

def save_market_structure(symbol: str, ms_df: pl.DataFrame):
    out_path = FEATURES_DIR / "market_structure.parquet"
    ms_df.write_parquet(out_path, compression="zstd")
    print(f"  Saved market structure → {out_path}")

# ==================== 2.4 LIQUIDITY SWEEPS ====================
def detect_liquidity_sweeps(df: pl.DataFrame, swings: pl.DataFrame) -> pl.DataFrame:
    """Simple liquidity sweep detection."""
    sweeps = []
    if swings.is_empty():
        return pl.DataFrame(schema={"time": pl.Datetime, "sweep_type": pl.Utf8, "t1": pl.Datetime})

    swing_lows = swings.filter(pl.col("swing_type") == "low").sort("time")
    swing_highs = swings.filter(pl.col("swing_type") == "high").sort("time")

    for i in range(1, len(df)):
        curr = df.row(i, named=True)
        prev = df.row(i-1, named=True)

        # Bullish sweep: broke previous swing low then closed back above
        if swing_lows.height > 0:
            last_low_time = swing_lows["time"][-1]
            last_low_price = swing_lows["low"][-1]
            if prev["low"] < last_low_price and curr["close"] > last_low_price:
                sweeps.append({
                    "time": curr["time"],
                    "sweep_type": "sweep_low",
                    "t1": curr["time"],
                })

        # Bearish sweep: broke previous swing high then closed back below
        if swing_highs.height > 0:
            last_high_time = swing_highs["time"][-1]
            last_high_price = swing_highs["high"][-1]
            if prev["high"] > last_high_price and curr["close"] < last_high_price:
                sweeps.append({
                    "time": curr["time"],
                    "sweep_type": "sweep_high",
                    "t1": curr["time"],
                })

    if not sweeps:
        return pl.DataFrame(schema={"time": pl.Datetime, "sweep_type": pl.Utf8, "t1": pl.Datetime})

    return pl.DataFrame(sweeps).unique(subset=["time", "sweep_type"]).sort("time")

def save_liquidity(symbol: str, liq_df: pl.DataFrame):
    out_path = FEATURES_DIR / "liquidity.parquet"
    liq_df.write_parquet(out_path, compression="zstd")
    print(f"  Saved liquidity sweeps → {out_path}")

# ==================== 2.5 ORDER BLOCKS ====================
def detect_order_blocks(df: pl.DataFrame, structure_df: pl.DataFrame) -> pl.DataFrame:
    """Basic order block detection after BOS."""
    obs = []
    if structure_df.is_empty():
        return pl.DataFrame(schema={
            "ob_id": pl.Int64, "start": pl.Datetime, "end": pl.Datetime,
            "type": pl.Utf8, "price_low": pl.Float64, "price_high": pl.Float64
        })

    bos_times = structure_df.filter(
        pl.col("structure").str.contains("BOS")
    )["time"].to_list()

    ob_id = 0
    for bos_time in bos_times:
        # Find the bar just before BOS
        idx = df["time"].search_sorted(bos_time) - 1
        if idx < 1:
            continue

        prev_candle = df.row(idx-1, named=True)
        bos_candle = df.row(idx, named=True)

        # Simple rule: last opposite candle before BOS
        if "BULL" in structure_df.filter(pl.col("time") == bos_time)["structure"][0]:
            ob_type = "bullish"
            price_low = prev_candle["low"]
            price_high = prev_candle["high"]
        else:
            ob_type = "bearish"
            price_low = prev_candle["low"]
            price_high = prev_candle["high"]

        obs.append({
            "ob_id": ob_id,
            "start": prev_candle["time"],
            "end": bos_candle["time"],
            "type": ob_type,
            "price_low": price_low,
            "price_high": price_high,
        })
        ob_id += 1

    if not obs:
        return pl.DataFrame(schema={
            "ob_id": pl.Int64, "start": pl.Datetime, "end": pl.Datetime,
            "type": pl.Utf8, "price_low": pl.Float64, "price_high": pl.Float64
        })

    return pl.DataFrame(obs)

def save_order_blocks(symbol: str, ob_df: pl.DataFrame):
    out_path = FEATURES_DIR / "order_blocks.parquet"
    ob_df.write_parquet(out_path, compression="zstd")
    print(f"  Saved order blocks → {out_path} ({len(ob_df)} blocks)")

# ==================== 2.6 FAIR VALUE GAPS ====================
def detect_fvg(df: pl.DataFrame) -> pl.DataFrame:
    """Three-candle FVG detection."""
    fvgs = []
    for i in range(2, len(df)):
        c0 = df.row(i, named=True)      # current
        c1 = df.row(i-1, named=True)    # middle
        c2 = df.row(i-2, named=True)    # 2 bars back

        # Bullish FVG
        if c0["low"] > c2["high"]:
            fvgs.append({
                "fvg_id": len(fvgs),
                "low": c2["high"],
                "high": c0["low"],
            })

        # Bearish FVG
        if c0["high"] < c2["low"]:
            fvgs.append({
                "fvg_id": len(fvgs),
                "low": c0["high"],
                "high": c2["low"],
            })

    if not fvgs:
        return pl.DataFrame(schema={"fvg_id": pl.Int64, "low": pl.Float64, "high": pl.Float64})

    return pl.DataFrame(fvgs)

def save_fvg(symbol: str, fvg_df: pl.DataFrame):
    out_path = FEATURES_DIR / "fvg.parquet"
    fvg_df.write_parquet(out_path, compression="zstd")
    print(f"  Saved FVGs → {out_path} ({len(fvg_df)} gaps)")

# ==================== MAIN PIPELINE ====================
def process_symbol(symbol: str):
    print(f"\n=== Processing {symbol} ===")

    raw_path = RAW_DIR / symbol / f"{symbol}_M1_raw.parquet"
    if not raw_path.exists():
        print(f"  No raw file found for {symbol}")
        return

    df = pl.read_parquet(raw_path)
    print(f"  Loaded {len(df):,} bars")

    # 2.1 Session Labels
    df = add_session_labels(df)
    save_session_labels(symbol, df)

    # 2.2 Swings
    swings = detect_swings(df)
    save_swings(symbol, swings)

    # 2.3 Market Structure
    ms = detect_market_structure(df, swings)
    save_market_structure(symbol, ms)

    # 2.4 Liquidity
    liq = detect_liquidity_sweeps(df, swings)
    save_liquidity(symbol, liq)

    # 2.5 Order Blocks
    obs = detect_order_blocks(df, ms)
    save_order_blocks(symbol, obs)

    # 2.6 FVG
    fvg = detect_fvg(df)
    save_fvg(symbol, fvg)

    print(f"  ✅ {symbol} features generated")

def main():
    print("=" * 60)
    print("Stage 2 — Feature Generation Layer (SMC)")
    print("=" * 60)

    for symbol in SYMBOLS:
        process_symbol(symbol)

    print("\n✅ Stage 2 complete. All feature parquet files saved in features/")

if __name__ == "__main__":
    main()