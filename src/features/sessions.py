from __future__ import annotations

from pathlib import Path

import pandas as pd

SESSION_WINDOWS = {
    "asian": (0, 8),
    "london": (8, 16),
    "new_york": (13, 21),
}


def label_sessions(frame: pd.DataFrame, pair: str | None = None) -> pd.DataFrame:
    """Label each candle with the active session using UTC timestamps."""
    df = frame.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)

    def _label(ts: pd.Timestamp) -> str:
        hour = ts.hour
        if SESSION_WINDOWS["new_york"][0] <= hour < SESSION_WINDOWS["new_york"][1]:
            return "new_york"
        if SESSION_WINDOWS["london"][0] <= hour < SESSION_WINDOWS["london"][1]:
            return "london"
        return "asian"

    pair_value = pair
    if pair_value is None and "pair" in df.columns and not df["pair"].empty:
        pair_value = df["pair"].iloc[0]

    out = pd.DataFrame(
        {
            "timestamp": df["timestamp"],
            "pair": pair_value,
            "session": df["timestamp"].map(_label),
        }
    )
    return out.reset_index(drop=True)


def save_sessions(
    frame: pd.DataFrame, path: str | Path, pair: str | None = None
) -> Path:
    out = label_sessions(frame, pair=pair)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(p, index=False)
    return p
