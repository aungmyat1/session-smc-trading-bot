from __future__ import annotations

from pathlib import Path

import pandas as pd


def detect_fvg(frame: pd.DataFrame, pair: str | None = None) -> pd.DataFrame:
    """Detect three-candle fair value gaps."""
    df = frame.copy().reset_index(drop=True)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    records: list[dict] = []

    for i in range(2, len(df)):
        older = df.loc[i - 2]
        cur = df.loc[i]
        if cur["low"] > older["high"]:
            records.append({
                "timestamp": cur["timestamp"],
                "pair": pair,
                "direction": "bullish",
                "low": float(older["high"]),
                "high": float(cur["low"]),
            })
        if cur["high"] < older["low"]:
            records.append({
                "timestamp": cur["timestamp"],
                "pair": pair,
                "direction": "bearish",
                "low": float(cur["high"]),
                "high": float(older["low"]),
            })

    return pd.DataFrame.from_records(records, columns=["timestamp", "pair", "direction", "low", "high"])


def save_fvg(frame: pd.DataFrame, path: str | Path, pair: str | None = None) -> Path:
    out = detect_fvg(frame, pair=pair)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(p, index=False)
    return p

