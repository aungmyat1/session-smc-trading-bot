#!/usr/bin/env python3
"""
scripts/build_timeframes.py
Timeframe Builder — Resamples tick data into M1, M5, M15, H1, H4, D1

Preserves: bid, ask, spread, volume
"""

import pandas as pd
from pathlib import Path

PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD"]
TIMEFRAMES = {
    "M1": "1min",
    "M5": "5min",
    "M15": "15min",
    "H1": "1H",
    "H4": "4H",
    "D1": "1D",
}

RAW_TICK_DIR = Path("data/processed")
OUTPUT_DIR = Path("data/processed")


def resample_ohlcv(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    """Resample tick data into OHLCV with bid/ask/spread."""
    df = df.set_index("timestamp")

    resampled = df.resample(rule).agg({"bid": "ohlc", "ask": "ohlc", "volume": "sum"})

    # Flatten multi-level columns
    resampled.columns = ["_".join(col).strip() for col in resampled.columns.values]

    # Calculate spread
    resampled["spread"] = resampled["ask_close"] - resampled["bid_close"]

    # Rename columns to standard OHLCV
    resampled = resampled.rename(
        columns={
            "bid_open": "open",
            "bid_high": "high",
            "bid_low": "low",
            "bid_close": "close",
        }
    )

    return resampled.reset_index()


def build_timeframes(pair: str):
    """Build all timeframes for a pair from tick data."""
    tick_file = RAW_TICK_DIR / pair / f"{pair}_TICK.parquet"
    if not tick_file.exists():
        print(f"  No tick data found for {pair}")
        return

    print(f"Building timeframes for {pair}...")
    df = pd.read_parquet(tick_file)

    for tf_name, rule in TIMEFRAMES.items():
        tf_df = resample_ohlcv(df, rule)
        tf_df["symbol"] = pair
        tf_df["timeframe"] = tf_name

        out_dir = OUTPUT_DIR / pair
        out_dir.mkdir(parents=True, exist_ok=True)

        output_file = out_dir / f"{pair}_{tf_name}.parquet"
        tf_df.to_parquet(output_file, compression="zstd", index=False)
        print(f"  ✅ {tf_name}: {len(tf_df):,} bars → {output_file}")


def main():
    print("=" * 60)
    print("Timeframe Builder")
    print("=" * 60)

    for pair in PAIRS:
        build_timeframes(pair)

    print("\n✅ All timeframes generated.")


if __name__ == "__main__":
    main()
