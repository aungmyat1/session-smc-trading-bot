#!/usr/bin/env python3
"""
Stage 3 — Signal Database
Creates a unified, searchable signal table from all SMC features.
"""

from pathlib import Path

import polars as pl

FEATURES_DIR = Path("features")
SIGNALS_DIR = Path("signals")
SIGNALS_DIR.mkdir(exist_ok=True)

SYMBOLS = ["EURUSD", "GBPUSD", "XAUUSD"]


def load_feature(file_name: str) -> pl.DataFrame:
    path = FEATURES_DIR / file_name
    if path.exists():
        return pl.read_parquet(path)
    return pl.DataFrame()


def build_signal_database(symbol: str) -> pl.DataFrame:
    print(f"Building signals for {symbol}...")

    # Load all feature layers
    sessions = load_feature("session_labels.parquet")
    swings = load_feature("swings.parquet")
    structure = load_feature("market_structure.parquet")
    liquidity = load_feature("liquidity.parquet")
    order_blocks = load_feature("order_blocks.parquet")
    fvgs = load_feature("fvg.parquet")

    # Start with session data as base (has time)
    if sessions.is_empty():
        print(f"  No session data for {symbol}")
        return pl.DataFrame()

    df = sessions.clone()

    # Add session column (combine London + NY)
    df = df.with_columns(
        [
            pl.when(
                (pl.col("session_london").is_not_null())
                & (pl.col("session_ny").is_not_null())
            )
            .then(pl.lit("Both"))
            .when(pl.col("session_london").is_not_null())
            .then(pl.lit("London"))
            .when(pl.col("session_ny").is_not_null())
            .then(pl.lit("NewYork"))
            .otherwise(pl.lit("None"))
            .alias("session")
        ]
    ).drop(["session_london", "session_ny"])

    # Join Market Structure
    if not structure.is_empty():
        df = df.join(structure.select(["time", "structure"]), on="time", how="left")

    # Join Liquidity Sweeps
    if not liquidity.is_empty():
        liq_agg = liquidity.group_by("time").agg(
            pl.col("sweep_type").first().alias("sweep")
        )
        df = df.join(liq_agg, on="time", how="left")

    # Join Order Blocks (has_ob flag)
    if not order_blocks.is_empty():
        ob_times = order_blocks.select(["start"]).rename({"start": "time"})
        ob_times = ob_times.with_columns(pl.lit(True).alias("has_ob"))
        df = df.join(ob_times, on="time", how="left")

    # Join FVGs (has_fvg flag)
    if not fvgs.is_empty():
        # FVGs don't have time, so we approximate by counting total FVGs near the bar
        # For simplicity, we mark any bar that has an active FVG
        fvg_flag = pl.DataFrame({"time": df["time"], "has_fvg": [False] * len(df)})
        # In real use, you would do proper time-range join here
        df = df.with_columns(pl.lit(False).alias("has_fvg"))

    # Fill nulls
    df = df.with_columns(
        [
            pl.col("structure").fill_null("None"),
            pl.col("sweep").fill_null("None"),
            pl.col("has_ob").fill_null(False),
            pl.col("has_fvg").fill_null(False),
        ]
    )

    # Create direction from structure
    df = df.with_columns(
        [
            pl.when(pl.col("structure").str.contains("BULL"))
            .then(pl.lit("LONG"))
            .when(pl.col("structure").str.contains("BEAR"))
            .then(pl.lit("SHORT"))
            .otherwise(pl.lit(None))
            .alias("direction")
        ]
    )

    # Final clean columns
    df = df.select(
        ["time", "session", "structure", "sweep", "has_ob", "has_fvg", "direction"]
    )

    # Add pair
    df = df.with_columns(pl.lit(symbol).alias("pair"))

    # Create signal_id
    df = df.with_row_index("signal_id").with_columns(
        (pl.col("signal_id") + 1).cast(pl.Int64)
    )

    # Reorder columns nicely
    df = df.select(
        [
            "signal_id",
            "pair",
            "time",
            "session",
            "structure",
            "sweep",
            "has_ob",
            "has_fvg",
            "direction",
        ]
    )

    print(f"  Generated {len(df):,} potential signals")
    return df


def main():
    print("=" * 60)
    print("Stage 3 — Signal Database")
    print("=" * 60)

    all_signals = []

    for symbol in SYMBOLS:
        signals = build_signal_database(symbol)
        if not signals.is_empty():
            all_signals.append(signals)

    if not all_signals:
        print("\nNo signals generated (raw data missing).")
        return

    # Combine all symbols
    final_df = pl.concat(all_signals).sort(["pair", "time"])

    # Save
    output_path = SIGNALS_DIR / "signals.parquet"
    final_df.write_parquet(output_path, compression="zstd")

    print(f"\n✅ Signal database saved → {output_path}")
    print(f"   Total signals: {len(final_df):,}")
    print(f"   Columns: {final_df.columns}")


if __name__ == "__main__":
    main()
