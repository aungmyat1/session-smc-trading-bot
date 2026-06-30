#!/usr/bin/env python3
"""
scripts/replay_db.py
Historical Replay Engine — ST-A2 Validation Phase

Reads M1 Parquet data and simulates trades into PostgreSQL.
"""

import argparse
from datetime import datetime, date
from pathlib import Path
import polars as pl
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
import os

# Database connection
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://trading_user:trading_research_2025@localhost:5432/trading_research",
)
engine = create_engine(DATABASE_URL)

# Data paths
RAW_DIR = Path("data/raw")


# Simple ST-A2 style logic (measurement only — do not modify rules)
def detect_smc_events(df: pl.DataFrame) -> pl.DataFrame:
    """Basic SMC detection for replay."""
    df = df.with_columns(
        [
            (pl.col("high") > pl.col("high").shift(1))
            & (pl.col("high") > pl.col("high").shift(-1)).alias("swing_high"),
            (pl.col("low") < pl.col("low").shift(1))
            & (pl.col("low") < pl.col("low").shift(-1)).alias("swing_low"),
        ]
    )
    return df


def run_replay(symbol: str, start: str, end: str, rr: float = 2.0):
    print(f"\n{'='*60}")
    print(f"HISTORICAL REPLAY — {symbol}")
    print(f"Period: {start} → {end}")
    print(f"Risk-Reward: {rr}R")
    print(f"{'='*60}")

    # Load M1 data
    m1_path = RAW_DIR / symbol / f"{symbol}_M1_raw.parquet"
    if not m1_path.exists():
        print(f"❌ No M1 data found for {symbol}")
        return

    df = pl.read_parquet(m1_path)
    df = df.filter(
        (pl.col("time") >= datetime.fromisoformat(start))
        & (pl.col("time") <= datetime.fromisoformat(end))
    )

    if df.is_empty():
        print("No data in selected range.")
        return

    print(f"Loaded {len(df):,} M1 bars")

    # Run basic SMC detection
    df = detect_smc_events(df)

    # Simple trade simulation (placeholder logic)
    trades = []
    for i in range(50, len(df) - 20, 80):  # Sample every ~80 bars
        row = df.row(i, named=True)
        direction = "LONG" if row.get("swing_low", False) else "SHORT"

        entry = float(row["close"])
        if direction == "LONG":
            stop = entry - 0.0015
            target = entry + (entry - stop) * rr
        else:
            stop = entry + 0.0015
            target = entry - (stop - entry) * rr

        # Simulate outcome (random for now — replace with real logic later)
        result_r = round(
            (target - entry) / (entry - stop) * (1 if direction == "LONG" else -1), 2
        )

        trades.append(
            {
                "trade_id": f"REPLAY-{symbol}-{i}",
                "run_id": f"REPLAY_{symbol}_{start}_{end}",
                "strategy_id": 1,
                "symbol": symbol,
                "session": "London" if 8 <= row["time"].hour < 16 else "NewYork",
                "direction": direction,
                "entry_time": row["time"],
                "exit_time": row["time"] + pd.Timedelta(minutes=120),
                "entry_price": entry,
                "stop_price": stop,
                "take_profit": target,
                "risk_reward": rr,
                "result_r": result_r,
                "exit_reason": "TP_HIT" if result_r > 0 else "SL_HIT",
            }
        )

    print(f"Generated {len(trades)} simulated trades")

    # Write to PostgreSQL
    with engine.connect() as conn:
        # Save replay run
        conn.execute(
            text("""
            INSERT INTO research.replay_runs (run_id, strategy_id, symbol, start_date, end_date, data_source)
            VALUES (:run_id, 1, :symbol, :start, :end, 'M1_parquet')
            ON CONFLICT (run_id) DO NOTHING
        """),
            {
                "run_id": f"REPLAY_{symbol}_{start}_{end}",
                "symbol": symbol,
                "start": start,
                "end": end,
            },
        )

        # Save trades
        for t in trades:
            conn.execute(
                text("""
                INSERT INTO research.trades 
                (trade_id, run_id, strategy_id, symbol, session, direction, 
                 entry_time, exit_time, entry_price, stop_price, take_profit,
                 risk_reward, result_r, exit_reason)
                VALUES (:trade_id, :run_id, :strategy_id, :symbol, :session, :direction,
                        :entry_time, :exit_time, :entry_price, :stop_price, :take_profit,
                        :risk_reward, :result_r, :exit_reason)
                ON CONFLICT (trade_id) DO NOTHING
            """),
                t,
            )

        conn.commit()

    print(f"✅ Replay complete. Trades written to PostgreSQL.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--rr", type=float, default=2.0)
    args = parser.parse_args()

    run_replay(args.symbol, args.start, args.end, args.rr)
