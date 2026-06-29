from __future__ import annotations

from pathlib import Path

import pandas as pd


def save_parquet(frame: pd.DataFrame, path: str | Path) -> Path:
    """Write a frame to Parquet and return the saved path."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(p, index=False)
    return p


def load_parquet(path: str | Path) -> pd.DataFrame:
    """Read a Parquet file into a pandas DataFrame."""
    return pd.read_parquet(Path(path))
