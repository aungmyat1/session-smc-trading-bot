from __future__ import annotations

from pathlib import Path

import pandas as pd

REQUIRED_COLUMNS = ("timestamp", "open", "high", "low", "close")


def load_m1_candles(path: Path | str, *, start: object | None = None, end: object | None = None) -> pd.DataFrame:
    source = Path(path)
    frame = pd.read_parquet(source) if source.suffix.lower() in {".parquet", ".pq"} else pd.read_csv(source)
    if "timestamp" not in frame and "time" in frame:
        frame = frame.rename(columns={"time": "timestamp"})
    missing = [column for column in REQUIRED_COLUMNS if column not in frame]
    if missing:
        raise ValueError(f"missing candle columns: {', '.join(missing)}")
    frame = frame.copy()
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    frame = frame.sort_values("timestamp", kind="stable").reset_index(drop=True)
    if frame["timestamp"].duplicated().any():
        raise ValueError("duplicate candle timestamps are not replayable")
    if start is not None:
        frame = frame[frame["timestamp"] >= pd.Timestamp(start)]
    if end is not None:
        frame = frame[frame["timestamp"] <= pd.Timestamp(end)]
    return frame.reset_index(drop=True)
