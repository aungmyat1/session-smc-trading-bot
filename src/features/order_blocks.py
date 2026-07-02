from __future__ import annotations

from pathlib import Path

import pandas as pd


def detect_order_blocks(frame: pd.DataFrame, structure: pd.DataFrame, pair: str | None = None) -> pd.DataFrame:
    """Find the last opposite candle before a BOS event."""
    candles = frame.copy().reset_index(drop=True)
    candles["timestamp"] = pd.to_datetime(candles["timestamp"], utc=True)
    events = structure.copy()
    if events.empty:
        return pd.DataFrame(columns=["pair", "time", "direction", "high", "low"])
    events["timestamp"] = pd.to_datetime(events["timestamp"], utc=True)

    records: list[dict] = []
    for _, ev in events.iterrows():
        if ev["structure"] != "BOS":
            continue
        direction = ev["direction"]
        candidates = []
        for _, candle in candles.iterrows():
            if candle["timestamp"] >= ev["timestamp"]:
                continue
            opposite = candle["close"] < candle["open"] if direction == "bullish" else candle["close"] > candle["open"]
            if opposite:
                candidates.append(candle)
        if not candidates:
            continue
        ob = candidates[-1]
        records.append({
            "pair": pair,
            "time": ob["timestamp"],
            "direction": direction,
            "high": float(ob["high"]),
            "low": float(ob["low"]),
        })

    return pd.DataFrame.from_records(records, columns=["pair", "time", "direction", "high", "low"])


def save_order_blocks(frame: pd.DataFrame, path: str | Path, pair: str | None = None) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(p, index=False)
    return p
