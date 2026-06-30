from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import pandas as pd

from .validator import validate_candles

REQUIRED_COLUMNS = ["timestamp", "open", "high", "low", "close", "volume", "spread"]


@dataclass(frozen=True)
class LoadedData:
    symbol: str
    timeframe: str
    frame: pd.DataFrame


def _standardize_frame(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    if "timestamp" not in frame.columns:
        if "time" in frame.columns:
            frame["timestamp"] = frame["time"]
        else:
            raise ValueError("missing timestamp column")
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    for col in ["open", "high", "low", "close", "volume", "spread"]:
        if col not in frame.columns:
            frame[col] = 0.0 if col == "spread" else 0
    frame = frame[REQUIRED_COLUMNS]
    frame = frame.sort_values("timestamp").reset_index(drop=True)
    return frame


def timeframe_to_freq(timeframe: str) -> str:
    tf = timeframe.upper().strip()
    if tf.endswith("M"):
        return f"{tf[:-1]}min"
    if tf.startswith("M"):
        return f"{tf[1:]}min"
    if tf.startswith("H"):
        return f"{tf[1:]}h"
    if tf.startswith("D"):
        return f"{tf[1:]}d"
    return "1min"


def load_candles(path: str | Path) -> pd.DataFrame:
    """Load a raw candle file from CSV or Parquet into a normalized frame."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(p)
    if p.suffix.lower() == ".parquet":
        frame = pd.read_parquet(p)
    else:
        frame = pd.read_csv(p)
    return _standardize_frame(frame)


def discover_raw_files(
    root: str | Path, symbol: str, timeframe: str = "M1"
) -> list[Path]:
    """Return raw files for a symbol and timeframe under the raw data tree."""
    root_path = Path(root)
    symbol = symbol.replace("/", "").replace("_", "").upper()
    timeframe = timeframe.upper()
    patterns = [
        f"**/{symbol}*{timeframe}*.parquet",
        f"**/{symbol[:3]}_{symbol[3:]}*{timeframe}*.parquet",
        f"**/{symbol}*{timeframe}*.csv",
        f"**/{symbol[:3]}_{symbol[3:]}*{timeframe}*.csv",
    ]
    matches: list[Path] = []
    for pattern in patterns:
        matches.extend(root_path.glob(pattern))
    return sorted({p.resolve() for p in matches})


def discover_symbol_timeframe(
    root: str | Path, symbol: str, preferred: str = "M1"
) -> tuple[str, list[Path]]:
    """Return the first available timeframe and matching files for a symbol."""
    candidates = [preferred, "M5", "M15", "H1", "H4"]
    for tf in candidates:
        files = discover_raw_files(root, symbol, timeframe=tf)
        if files:
            return tf, files
    return preferred, []


def load_symbol_history(
    symbol: str,
    root: str | Path,
    timeframe: str = "M1",
    validate: bool = True,
) -> LoadedData:
    """Load and optionally validate all raw files for one symbol."""
    actual_timeframe, files = discover_symbol_timeframe(
        root, symbol, preferred=timeframe
    )
    if not files:
        raise FileNotFoundError(
            f"no raw files found for {symbol} {timeframe} under {root}"
        )

    frames = [load_candles(path) for path in files]
    frame = pd.concat(frames, ignore_index=True)
    frame = frame.drop_duplicates(subset=["timestamp"], keep="last")
    frame = frame.sort_values("timestamp").reset_index(drop=True)

    report = validate_candles(frame, expected_freq=timeframe_to_freq(actual_timeframe))
    if validate and not report.ok:
        raise ValueError("invalid candle set: " + "; ".join(report.errors))

    return LoadedData(symbol=symbol, timeframe=actual_timeframe, frame=frame)
