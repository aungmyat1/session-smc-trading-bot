"""
Replay adapter — loads processed Parquet and exposes the same bar-list interface
used by backtest_session_liquidity.py and replay_6m.py.

This allows all existing backtest scripts to use Parquet data without modification:
    from scripts.replay_parquet import load_m15, load_h4, load_h1

The returned lists match the format of the existing CSV loaders:
    [{"time": "2021-06-21T00:00:00Z", "open": 1.1900, "high": ..., "low": ..., "close": ..., "volume": ...}, ...]

Usage in backtest scripts:
    # Replace:
    #   bars_m15 = load_csv("data/historical/EUR_USD_M15.csv")
    # With:
    #   from scripts.replay_parquet import load_m15
    #   bars_m15 = load_m15("EURUSD", start="2021-01-01", end="2026-06-19")
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA_PROC = ROOT / "data" / "processed"
DATA_HIST = ROOT / "data" / "historical"

_CSV_SYM = {
    "EURUSD": "EUR_USD",
    "GBPUSD": "GBP_USD",
}


def _load_parquet(sym: str, tf: str, start: str | None = None, end: str | None = None) -> list[dict]:
    path = DATA_PROC / sym / f"{tf}.parquet"
    if not path.exists():
        return []
    df = pd.read_parquet(path, columns=["timestamp_utc", "open", "high", "low", "close", "volume"])
    df["time"] = pd.to_datetime(df["timestamp_utc"], utc=True).dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    df = df.drop(columns=["timestamp_utc"])
    if start:
        df = df[df["time"] >= start]
    if end:
        df = df[df["time"] <= end]
    return df[["time", "open", "high", "low", "close", "volume"]].to_dict("records")


def _load_csv_fallback(sym: str, tf: str, start: str | None = None, end: str | None = None) -> list[dict]:
    csv_sym = _CSV_SYM.get(sym, sym.replace("USD", "_USD"))
    path = DATA_HIST / f"{csv_sym}_{tf}.csv"
    if not path.exists():
        raise FileNotFoundError(f"No processed Parquet or CSV found for {sym} {tf}")
    df = pd.read_csv(path)
    df.columns = [c.lower() for c in df.columns]
    if start:
        df = df[df["time"] >= start]
    if end:
        df = df[df["time"] <= end]
    return df[["time", "open", "high", "low", "close", "volume"]].to_dict("records")


def _load(sym: str, tf: str, start: str | None = None, end: str | None = None) -> list[dict]:
    bars = _load_parquet(sym, tf, start, end)
    if bars:
        return bars
    return _load_csv_fallback(sym, tf, start, end)


def load_m15(sym: str, start: str | None = None, end: str | None = None) -> list[dict]:
    """Load M15 bars for symbol. Falls back to CSV if Parquet not built."""
    return _load(sym, "M15", start, end)


def load_h1(sym: str, start: str | None = None, end: str | None = None) -> list[dict]:
    """Load H1 bars for symbol."""
    return _load(sym, "H1", start, end)


def load_h4(sym: str, start: str | None = None, end: str | None = None) -> list[dict]:
    """Load H4 bars for symbol."""
    return _load(sym, "H4", start, end)


def load_d1(sym: str, start: str | None = None, end: str | None = None) -> list[dict]:
    """Load D1 bars for symbol. Parquet-only (no CSV fallback for D1)."""
    return _load_parquet(sym, "D1", start, end)


def available_range(sym: str, tf: str) -> tuple[str | None, str | None]:
    """Return (start_str, end_str) for the available date range of a symbol/TF."""
    bars = _load(sym, tf)
    if not bars:
        return None, None
    return bars[0]["time"], bars[-1]["time"]
