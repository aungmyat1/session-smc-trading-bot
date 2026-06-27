from __future__ import annotations

from pathlib import Path

import pandas as pd


def detect_swings(frame: pd.DataFrame, pair: str | None = None, lookback: int = 1) -> pd.DataFrame:
    """Detect swing highs/lows using centered local extrema."""
    if lookback < 1:
        raise ValueError("lookback must be >= 1")
    df = frame.copy().reset_index(drop=True)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)

    records: list[dict] = []
    for i in range(lookback, len(df) - lookback):
        high = df.loc[i, "high"]
        low = df.loc[i, "low"]
        window_highs = df.loc[i - lookback : i + lookback, "high"]
        window_lows = df.loc[i - lookback : i + lookback, "low"]
        ts = df.loc[i, "timestamp"]
        if high == window_highs.max() and high > df.loc[i - 1, "high"] and high > df.loc[i + 1, "high"]:
            records.append({"timestamp": ts, "pair": pair, "price": float(high), "swing_type": "swing_high"})
        if low == window_lows.min() and low < df.loc[i - 1, "low"] and low < df.loc[i + 1, "low"]:
            records.append({"timestamp": ts, "pair": pair, "price": float(low), "swing_type": "swing_low"})

    return pd.DataFrame.from_records(records, columns=["timestamp", "pair", "price", "swing_type"])


def save_swings(frame: pd.DataFrame, path: str | Path, pair: str | None = None, lookback: int = 1) -> Path:
    out = detect_swings(frame, pair=pair, lookback=lookback)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(p, index=False)
    return p

