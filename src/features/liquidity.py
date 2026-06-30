from __future__ import annotations

from pathlib import Path

import pandas as pd


def detect_liquidity_sweeps(
    frame: pd.DataFrame, pair: str | None = None
) -> pd.DataFrame:
    """Detect simple bullish/bearish liquidity sweeps against the prior candle."""
    df = frame.copy().reset_index(drop=True)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    records: list[dict] = []

    for i in range(1, len(df)):
        prev = df.loc[i - 1]
        cur = df.loc[i]
        if cur["low"] < prev["low"] and cur["close"] > prev["low"]:
            records.append(
                {
                    "timestamp": cur["timestamp"],
                    "pair": pair,
                    "sweep_type": "bullish",
                    "liquidity_level": float(prev["low"]),
                }
            )
        if cur["high"] > prev["high"] and cur["close"] < prev["high"]:
            records.append(
                {
                    "timestamp": cur["timestamp"],
                    "pair": pair,
                    "sweep_type": "bearish",
                    "liquidity_level": float(prev["high"]),
                }
            )

    return pd.DataFrame.from_records(
        records, columns=["timestamp", "pair", "sweep_type", "liquidity_level"]
    )


def save_liquidity(
    frame: pd.DataFrame, path: str | Path, pair: str | None = None
) -> Path:
    out = detect_liquidity_sweeps(frame, pair=pair)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(p, index=False)
    return p
