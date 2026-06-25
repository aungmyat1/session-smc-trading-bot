#!/usr/bin/env python3
"""
Stage 1 — Raw Market Data Layer (Chunked M1 downloader)
Downloads clean historical M1 data for EURUSD, GBPUSD, XAUUSD (2020 → present)
and stores it as Parquet files.
"""

import os
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import polars as pl
import yfinance as yf

# Configuration
SYMBOLS = ["EURUSD", "GBPUSD", "XAUUSD"]
TIMEFRAME = "1m"
START_DATE = datetime(2020, 1, 1)
END_DATE = datetime.now()

RAW_DIR = Path("data/raw")

# yfinance ticker mapping
YF_TICKERS = {
    "EURUSD": "EURUSD=X",
    "GBPUSD": "GBPUSD=X",
    "XAUUSD": "GC=F",        # Gold futures (closest to XAUUSD)
}

MAX_DAYS_PER_REQUEST = 7

def get_yf_ticker(symbol: str) -> str:
    return YF_TICKERS.get(symbol, f"{symbol}=X")

def download_chunk(ticker: str, start: datetime, end: datetime) -> pl.DataFrame:
    """Download a single chunk of M1 data."""
    try:
        df = yf.download(
            tickers=ticker,
            start=start.strftime("%Y-%m-%d"),
            end=end.strftime("%Y-%m-%d"),
            interval=TIMEFRAME,
            progress=False,
            auto_adjust=True,
        )
    except Exception:
        return pl.DataFrame()

    if df.empty:
        return pl.DataFrame()

    # yfinance returns multi-level columns when using a list of tickers
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df.rename(columns={
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Volume": "volume",
    }).reset_index().rename(columns={"Datetime": "time"})

    df = df[["time", "open", "high", "low", "close", "volume"]]

    pl_df = pl.from_pandas(df)
    pl_df = pl_df.with_columns([
        pl.col("time").cast(pl.Datetime("us")),
        pl.col("open").cast(pl.Float64),
        pl.col("high").cast(pl.Float64),
        pl.col("low").cast(pl.Float64),
        pl.col("close").cast(pl.Float64),
        pl.col("volume").cast(pl.Int64).fill_null(0),
    ])

    return pl_df

def download_symbol(symbol: str) -> pl.DataFrame:
    """Download full M1 history using multiple chunked requests."""
    ticker = get_yf_ticker(symbol)
    print(f"Downloading {symbol} ({ticker}) from {START_DATE.date()} to {END_DATE.date()}...")

    all_data = []
    current = START_DATE

    while current < END_DATE:
        chunk_end = min(current + timedelta(days=MAX_DAYS_PER_REQUEST), END_DATE)
        print(f"  Fetching chunk: {current.date()} → {chunk_end.date()}", end=" ")

        chunk = download_chunk(ticker, current, chunk_end)
        if not chunk.is_empty():
            all_data.append(chunk)
            print(f"({len(chunk):,} rows)")
        else:
            print("(no data)")

        current = chunk_end

    if not all_data:
        print(f"  No data collected for {symbol}")
        return pl.DataFrame()

    # Concatenate and clean
    df = pl.concat(all_data)
    df = df.unique(subset=["time"]).sort("time")

    print(f"  Total: {len(df):,} rows for {symbol}")
    return df

def save_parquet(df: pl.DataFrame, symbol: str):
    """Save DataFrame to Parquet."""
    if df.is_empty():
        return

    out_dir = RAW_DIR / symbol
    out_dir.mkdir(parents=True, exist_ok=True)

    filename = out_dir / f"{symbol}_M1_raw.parquet"
    df.write_parquet(filename, compression="zstd")
    print(f"  Saved → {filename}")

def main():
    print("=" * 60)
    print("Stage 1 — Raw Market Data Layer (Chunked)")
    print(f"Symbols: {', '.join(SYMBOLS)}")
    print(f"Timeframe: M1 | Period: {START_DATE.date()} → {END_DATE.date()}")
    print("=" * 60)

    for symbol in SYMBOLS:
        df = download_symbol(symbol)
        if not df.is_empty():
            save_parquet(df, symbol)
        print()

    print("✅ Stage 1 complete. Raw data saved in data/raw/")

if __name__ == "__main__":
    main()