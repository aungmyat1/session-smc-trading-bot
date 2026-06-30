#!/usr/bin/env python3
"""
scripts/import_parquet.py
Import Parquet data into PostgreSQL (candles, SMC events, trades).
"""

import os
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://trading_user:trading_research_2025@localhost:5432/trading_research",
)
engine = create_engine(DATABASE_URL)


def import_candles(parquet_path: str, symbol: str, timeframe: str):
    """Import candle data from Parquet."""
    df = pd.read_parquet(parquet_path)
    df["symbol"] = symbol
    df["timeframe"] = timeframe
    df["source"] = "parquet_import"
    df.to_sql(
        "candles",
        engine,
        schema="market",
        if_exists="append",
        index=False,
        chunksize=5000,
    )
    print(f"Imported {len(df):,} candles for {symbol} {timeframe}")


def import_smc_events(parquet_path: str):
    """Import SMC events."""
    df = pd.read_parquet(parquet_path)
    df.to_sql(
        "smc_events",
        engine,
        schema="market",
        if_exists="append",
        index=False,
        chunksize=2000,
    )
    print(f"Imported {len(df):,} SMC events")


if __name__ == "__main__":
    print("Parquet import script ready. Usage example:")
    print("import_candles('data/EURUSD/m1.parquet', 'EURUSD', 'M1')")
