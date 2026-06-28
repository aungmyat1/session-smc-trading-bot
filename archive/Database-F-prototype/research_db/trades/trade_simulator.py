#!/usr/bin/env python3
"""
trade_simulator.py
Main entry point for Stage 4 — Trade Database Simulation Engine
"""

from pathlib import Path
from typing import List, Dict
import polars as pl

# When run directly, import from same folder
try:
    from .trade_engine import simulate_trade
except ImportError:
    from trade_engine import simulate_trade

SIGNALS_PATH = Path("signals/signals.parquet")
RAW_DIR = Path("data/raw")
TRADES_DIR = Path("research_db/trades")
TRADES_DIR.mkdir(parents=True, exist_ok=True)

SYMBOLS = ["EURUSD", "GBPUSD", "XAUUSD"]


def load_raw_data(symbol: str) -> pl.DataFrame:
    """Load raw M1 data for a symbol."""
    path = RAW_DIR / symbol / f"{symbol}_M1_raw.parquet"
    if not path.exists():
        return pl.DataFrame()
    return pl.read_parquet(path)


def load_signals() -> pl.DataFrame:
    """Load all signals from Stage 3."""
    if not SIGNALS_PATH.exists():
        print("No signals.parquet found. Run Stage 3 first.")
        return pl.DataFrame()
    return pl.read_parquet(SIGNALS_PATH)


def run_simulation(rr: float = 2.0) -> pl.DataFrame:
    """
    Run the full trade simulation across all signals.
    """
    print("=" * 60)
    print("Stage 4 — Trade Database Simulation Engine")
    print(f"Risk-Reward Ratio: {rr}R")
    print("=" * 60)

    signals_df = load_signals()
    if signals_df.is_empty():
        return pl.DataFrame()

    all_trades: List[Dict] = []

    for symbol in SYMBOLS:
        symbol_signals = signals_df.filter(pl.col("pair") == symbol)
        if symbol_signals.is_empty():
            continue

        candles = load_raw_data(symbol)
        if candles.is_empty():
            print(f"  No raw data for {symbol} — skipping")
            continue

        print(f"\nSimulating {len(symbol_signals):,} signals for {symbol}...")

        for signal_row in symbol_signals.iter_rows(named=True):
            trade = simulate_trade(signal_row, candles, rr_multiple=rr)
            if trade:
                all_trades.append(trade)

    if not all_trades:
        print("\nNo trades could be simulated.")
        return pl.DataFrame()

    trades_df = pl.DataFrame(all_trades)

    # Assign trade_ids
    trades_df = trades_df.with_row_index("trade_id").with_columns(
        (pl.col("trade_id") + 1).cast(pl.Int64)
    )

    # Save results
    output_path = TRADES_DIR / "trades.parquet"
    trades_df.write_parquet(output_path, compression="zstd")

    print("\n✅ Simulation complete!")
    print(f"   Total trades simulated: {len(trades_df):,}")
    print(f"   Saved to: {output_path}")

    # Quick summary
    win_rate = (trades_df["outcome"] == "WIN").mean() * 100
    avg_r = trades_df["result_r"].mean()
    print("\n📊 Quick Stats:")
    print(f"   Win Rate: {win_rate:.1f}%")
    print(f"   Average R-multiple: {avg_r:.2f}R")

    return trades_df


if __name__ == "__main__":
    run_simulation(rr=2.0)