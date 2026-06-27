from __future__ import annotations

from pathlib import Path

import pandas as pd


def build_structure(frame: pd.DataFrame, swings: pd.DataFrame, pair: str | None = None) -> pd.DataFrame:
    """Generate HH/HL/LH/LL plus BOS/CHOCH events from swings and closes."""
    candles = frame.copy().reset_index(drop=True)
    candles["timestamp"] = pd.to_datetime(candles["timestamp"], utc=True)
    swing_df = swings.copy()
    if not swing_df.empty:
        swing_df["timestamp"] = pd.to_datetime(swing_df["timestamp"], utc=True)
        swing_df = swing_df.sort_values("timestamp").reset_index(drop=True)

    records: list[dict] = []
    last_high = None
    last_low = None
    last_trend = "neutral"
    active_high = None
    active_low = None

    for _, sw in swing_df.iterrows():
        price = float(sw["price"])
        ts = sw["timestamp"]
        if sw["swing_type"] == "swing_high":
            structure = "HH" if last_high is None or price >= last_high else "LH"
            direction = "bullish" if structure == "HH" else "bearish"
            records.append({"timestamp": ts, "pair": pair, "structure": structure, "direction": direction})
            last_high = price
            active_high = price
        elif sw["swing_type"] == "swing_low":
            structure = "HL" if last_low is None or price > last_low else "LL"
            direction = "bullish" if structure == "HL" else "bearish"
            records.append({"timestamp": ts, "pair": pair, "structure": structure, "direction": direction})
            last_low = price
            active_low = price

    if active_high is None and active_low is None:
        return pd.DataFrame(columns=["timestamp", "pair", "structure", "direction"])

    swing_lookup = swing_df.set_index("timestamp") if not swing_df.empty else pd.DataFrame()
    for _, candle in candles.iterrows():
        ts = candle["timestamp"]
        close = float(candle["close"])
        high = active_high
        low = active_low
        if high is not None and close > high:
            structure = "CHOCH" if last_trend == "bearish" else "BOS"
            records.append({"timestamp": ts, "pair": pair, "structure": structure, "direction": "bullish"})
            last_trend = "bullish"
            active_high = close
        if low is not None and close < low:
            structure = "CHOCH" if last_trend == "bullish" else "BOS"
            records.append({"timestamp": ts, "pair": pair, "structure": structure, "direction": "bearish"})
            last_trend = "bearish"
            active_low = close

    out = pd.DataFrame.from_records(records, columns=["timestamp", "pair", "structure", "direction"])
    if not out.empty:
        out = out.drop_duplicates().sort_values("timestamp").reset_index(drop=True)
    return out


def save_structure(frame: pd.DataFrame, path: str | Path, pair: str | None = None) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(p, index=False)
    return p

