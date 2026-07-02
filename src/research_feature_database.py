from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd

from src.analytics.duckdb_store import DuckDBStore


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RAW_ROOT = ROOT / "data" / "raw"
DEFAULT_PROCESSED_ROOT = ROOT / "data" / "processed"
DEFAULT_OUTPUT_ROOT = ROOT / "research_db"
DEFAULT_STAGE_ROOT = DEFAULT_OUTPUT_ROOT / "data" / "processed"


@dataclass(frozen=True)
class FeatureDatabasePaths:
    raw_root: Path = DEFAULT_RAW_ROOT
    processed_root: Path = DEFAULT_PROCESSED_ROOT
    output_root: Path = DEFAULT_OUTPUT_ROOT

    @property
    def stage_root(self) -> Path:
        return self.output_root / "data" / "processed"

    @property
    def duckdb_path(self) -> Path:
        return self.output_root / "feature_database.duckdb"

    @property
    def parquet_path(self) -> Path:
        return self.output_root / "feature_database.parquet"


def _normalize_source_frame(frame: pd.DataFrame, symbol: str) -> pd.DataFrame:
    df = frame.copy()

    timestamp_col = None
    for candidate in ("timestamp", "timestamp_utc", "time", "datetime"):
        if candidate in df.columns:
            timestamp_col = candidate
            break
    if timestamp_col is None:
        raise ValueError(f"{symbol}: missing timestamp column")

    df["timestamp"] = pd.to_datetime(df[timestamp_col], utc=True)
    if "pair" not in df.columns:
        df["pair"] = symbol
    df["pair"] = df["pair"].fillna(symbol).astype(str)

    for col in ("open", "high", "low", "close"):
        if col not in df.columns:
            raise ValueError(f"{symbol}: missing required column {col}")
    if "volume" not in df.columns:
        df["volume"] = 0.0

    out = df[["timestamp", "pair", "open", "high", "low", "close", "volume"]].copy()
    out = out.sort_values("timestamp").drop_duplicates(subset=["timestamp", "pair"], keep="last").reset_index(drop=True)
    return out


def _read_candle_file(path: Path, symbol: str) -> pd.DataFrame:
    if path.suffix.lower() == ".parquet":
        frame = pd.read_parquet(path)
    else:
        frame = pd.read_csv(path)
    return _normalize_source_frame(frame, symbol)


def discover_m1_sources(symbol: str, raw_root: Path, processed_root: Path) -> list[Path]:
    symbol = symbol.upper().strip()
    matches: set[Path] = set()

    if raw_root.exists():
        patterns = [
            f"**/{symbol}_M1*.csv",
            f"**/{symbol}*M1*.csv",
            f"**/{symbol[:3]}_{symbol[3:]}*M1*.csv",
            f"**/{symbol}*.parquet",
        ]
        for pattern in patterns:
            matches.update(raw_root.glob(pattern))

    if matches:
        return sorted(p.resolve() for p in matches if p.is_file())

    fallback_candidates = [
        processed_root / symbol / "M1.parquet",
        ROOT / "research_db" / "candles" / f"{symbol}_M1.parquet",
        ROOT / "data" / "historical" / f"{symbol}_M1.parquet",
    ]
    return [path for path in fallback_candidates if path.exists()]


def load_symbol_m1(symbol: str, paths: FeatureDatabasePaths) -> pd.DataFrame:
    sources = discover_m1_sources(symbol, paths.raw_root, paths.processed_root)
    if not sources:
        raise FileNotFoundError(f"No M1 sources found for {symbol}")

    frames = [_read_candle_file(path, symbol) for path in sources]
    frame = pd.concat(frames, ignore_index=True)
    frame = frame.sort_values("timestamp").drop_duplicates(subset=["timestamp", "pair"], keep="last").reset_index(drop=True)
    return frame


def label_sessions(frame: pd.DataFrame) -> pd.DataFrame:
    df = frame.copy()
    hours = df["timestamp"].dt.hour
    session = pd.Series("None", index=df.index, dtype="object")
    session[(hours >= 12) & (hours < 16)] = "Both"
    session[(hours >= 7) & (hours < 12)] = "London"
    session[(hours >= 12) & (hours < 17) & (session == "None")] = "NewYork"
    df["session"] = session
    return df


def detect_swings(frame: pd.DataFrame, n: int = 5) -> pd.DataFrame:
    if n < 1:
        raise ValueError("swing lookback n must be >= 1")

    df = frame.copy()
    window = 2 * n + 1
    df["swing_high"] = df["high"].eq(df["high"].rolling(window=window, center=True, min_periods=window).max()).fillna(False)
    df["swing_low"] = df["low"].eq(df["low"].rolling(window=window, center=True, min_periods=window).min()).fillna(False)
    return df


def annotate_structure(frame: pd.DataFrame) -> pd.DataFrame:
    df = frame.copy()
    df["structure"] = pd.Series([None] * len(df), dtype="object")
    df["bos"] = False
    df["choch"] = False
    df["direction"] = pd.Series([None] * len(df), dtype="object")

    prev_swing_high = None
    prev_swing_low = None
    trend = "neutral"
    last_broken_high = None
    last_broken_low = None

    for idx, row in df.iterrows():
        if bool(row["swing_high"]):
            if prev_swing_high is None:
                label = "HH"
                direction = "bullish"
            else:
                label = "HH" if float(row["high"]) > prev_swing_high else "LH"
                direction = "bullish" if label == "HH" else "bearish"
            df.at[idx, "structure"] = label
            df.at[idx, "direction"] = direction
            prev_swing_high = float(row["high"])

        if bool(row["swing_low"]):
            if prev_swing_low is None:
                label = "HL"
                direction = "bullish"
            else:
                label = "HL" if float(row["low"]) > prev_swing_low else "LL"
                direction = "bullish" if label == "HL" else "bearish"
            df.at[idx, "structure"] = label
            df.at[idx, "direction"] = direction
            prev_swing_low = float(row["low"])

        close = float(row["close"])
        if prev_swing_high is not None and close > prev_swing_high and (last_broken_high is None or prev_swing_high > last_broken_high):
            event = "CHOCH" if trend == "bearish" else "BOS"
            df.at[idx, "structure"] = event
            df.at[idx, "bos"] = event == "BOS"
            df.at[idx, "choch"] = event == "CHOCH"
            df.at[idx, "direction"] = "bullish"
            trend = "bullish"
            last_broken_high = prev_swing_high

        if prev_swing_low is not None and close < prev_swing_low and (last_broken_low is None or prev_swing_low < last_broken_low):
            event = "CHOCH" if trend == "bullish" else "BOS"
            df.at[idx, "structure"] = event
            df.at[idx, "bos"] = event == "BOS"
            df.at[idx, "choch"] = event == "CHOCH"
            df.at[idx, "direction"] = "bearish"
            trend = "bearish"
            last_broken_low = prev_swing_low

    return df


def annotate_liquidity_sweeps(frame: pd.DataFrame) -> pd.DataFrame:
    df = frame.copy()
    prev_swing_high = df["high"].where(df["swing_high"]).ffill().shift(1)
    prev_swing_low = df["low"].where(df["swing_low"]).ffill().shift(1)

    df["sweep_high"] = (df["high"] > prev_swing_high) & (df["close"] < prev_swing_high)
    df["sweep_low"] = (df["low"] < prev_swing_low) & (df["close"] > prev_swing_low)
    return df


def annotate_order_blocks(frame: pd.DataFrame) -> pd.DataFrame:
    df = frame.copy()
    df["has_order_block"] = False
    df["ob_type"] = pd.Series([None] * len(df), dtype="object")
    df["ob_high"] = pd.Series([None] * len(df), dtype="float64")
    df["ob_low"] = pd.Series([None] * len(df), dtype="float64")

    last_bearish_idx: int | None = None
    last_bullish_idx: int | None = None

    for idx, row in df.iterrows():
        if float(row["close"]) < float(row["open"]):
            last_bearish_idx = idx
        elif float(row["close"]) > float(row["open"]):
            last_bullish_idx = idx

        if not row["bos"] and not row["choch"]:
            continue
        direction = row["direction"]
        if direction not in {"bullish", "bearish"}:
            continue

        if direction == "bullish":
            ob_idx = last_bearish_idx
        else:
            ob_idx = last_bullish_idx

        if ob_idx is None or bool(df.at[ob_idx, "has_order_block"]):
            continue

        df.at[ob_idx, "has_order_block"] = True
        df.at[ob_idx, "ob_type"] = direction
        df.at[ob_idx, "ob_high"] = float(df.at[ob_idx, "high"])
        df.at[ob_idx, "ob_low"] = float(df.at[ob_idx, "low"])
        if pd.isna(df.at[ob_idx, "direction"]):
            df.at[ob_idx, "direction"] = direction

    return df


def annotate_fvg(frame: pd.DataFrame) -> pd.DataFrame:
    df = frame.copy()
    df["has_fvg"] = False
    df["fvg_type"] = pd.Series([None] * len(df), dtype="object")
    df["fvg_high"] = pd.Series([None] * len(df), dtype="float64")
    df["fvg_low"] = pd.Series([None] * len(df), dtype="float64")

    bullish = df["low"].shift(-1) > df["high"].shift(1)
    bearish = df["high"].shift(-1) < df["low"].shift(1)

    for idx in df.index[1:-1]:
        if bool(bullish.iloc[idx]):
            df.at[idx, "has_fvg"] = True
            df.at[idx, "fvg_type"] = "bullish"
            df.at[idx, "fvg_low"] = float(df.at[idx - 1, "high"])
            df.at[idx, "fvg_high"] = float(df.at[idx + 1, "low"])
            if pd.isna(df.at[idx, "direction"]):
                df.at[idx, "direction"] = "bullish"
        elif bool(bearish.iloc[idx]):
            df.at[idx, "has_fvg"] = True
            df.at[idx, "fvg_type"] = "bearish"
            df.at[idx, "fvg_low"] = float(df.at[idx + 1, "high"])
            df.at[idx, "fvg_high"] = float(df.at[idx - 1, "low"])
            if pd.isna(df.at[idx, "direction"]):
                df.at[idx, "direction"] = "bearish"

    return df


def build_symbol_feature_frame(symbol: str, paths: FeatureDatabasePaths, swing_lookback: int = 5) -> pd.DataFrame:
    base = load_symbol_m1(symbol, paths)
    base = label_sessions(base)
    base = detect_swings(base, n=swing_lookback)
    base = annotate_structure(base)
    base = annotate_liquidity_sweeps(base)
    base = annotate_order_blocks(base)
    base = annotate_fvg(base)

    final_cols = [
        "timestamp",
        "pair",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "session",
        "swing_high",
        "swing_low",
        "structure",
        "bos",
        "choch",
        "sweep_high",
        "sweep_low",
        "has_order_block",
        "ob_type",
        "ob_high",
        "ob_low",
        "has_fvg",
        "fvg_type",
        "fvg_high",
        "fvg_low",
        "direction",
    ]
    out = base[final_cols].copy()
    out["swing_high"] = out["swing_high"].fillna(False).astype(bool)
    out["swing_low"] = out["swing_low"].fillna(False).astype(bool)
    out["bos"] = out["bos"].fillna(False).astype(bool)
    out["choch"] = out["choch"].fillna(False).astype(bool)
    out["sweep_high"] = out["sweep_high"].fillna(False).astype(bool)
    out["sweep_low"] = out["sweep_low"].fillna(False).astype(bool)
    out["has_order_block"] = out["has_order_block"].fillna(False).astype(bool)
    out["has_fvg"] = out["has_fvg"].fillna(False).astype(bool)
    return out


def _stage_views(frame: pd.DataFrame) -> dict[str, pd.DataFrame]:
    def filtered(columns: list[str], predicate) -> pd.DataFrame:
        records = [
            {column: row[column] for column in columns}
            for _, row in frame.iterrows()
            if predicate(row)
        ]
        return pd.DataFrame.from_records(records, columns=columns)

    candles_labeled = frame[["timestamp", "pair", "open", "high", "low", "close", "volume", "session"]].copy()
    structure = frame[["timestamp", "pair", "swing_high", "swing_low", "structure", "bos", "choch", "direction"]].copy()
    sweeps = filtered(["timestamp", "pair", "sweep_high", "sweep_low", "direction"], lambda row: bool(row["sweep_high"] or row["sweep_low"]))
    order_blocks = filtered(
        ["timestamp", "pair", "has_order_block", "ob_type", "ob_high", "ob_low", "direction"],
        lambda row: bool(row["has_order_block"]),
    )
    fvgs = filtered(
        ["timestamp", "pair", "has_fvg", "fvg_type", "fvg_high", "fvg_low", "direction"],
        lambda row: bool(row["has_fvg"]),
    )
    return {
        "candles_labeled": candles_labeled,
        "structure": structure,
        "sweeps": sweeps,
        "order_blocks": order_blocks,
        "fvg": fvgs,
        "feature_database": frame.copy(),
    }


def _save_parquet(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path, index=False)


def build_feature_database(
    symbols: Iterable[str],
    paths: FeatureDatabasePaths | None = None,
    swing_lookback: int = 5,
) -> dict[str, pd.DataFrame]:
    paths = paths or FeatureDatabasePaths()
    paths.output_root.mkdir(parents=True, exist_ok=True)
    paths.stage_root.mkdir(parents=True, exist_ok=True)

    stage_buckets: dict[str, list[pd.DataFrame]] = {
        "candles_labeled": [],
        "structure": [],
        "sweeps": [],
        "order_blocks": [],
        "fvg": [],
        "feature_database": [],
    }

    for symbol in symbols:
        frame = build_symbol_feature_frame(symbol, paths, swing_lookback=swing_lookback)
        views = _stage_views(frame)
        for key, view in views.items():
            stage_buckets[key].append(view)

    outputs: dict[str, pd.DataFrame] = {}
    for key, frames in stage_buckets.items():
        if frames:
            combined = pd.concat(frames, ignore_index=True)
            combined = combined.sort_values(["pair", "timestamp"]).reset_index(drop=True)
        else:
            combined = pd.DataFrame()
        outputs[key] = combined

    _save_parquet(outputs["candles_labeled"], paths.stage_root / "candles_labeled.parquet")
    _save_parquet(outputs["structure"], paths.stage_root / "structure.parquet")
    _save_parquet(outputs["sweeps"], paths.stage_root / "sweeps.parquet")
    _save_parquet(outputs["order_blocks"], paths.stage_root / "order_blocks.parquet")
    _save_parquet(outputs["fvg"], paths.stage_root / "fvg.parquet")
    _save_parquet(outputs["feature_database"], paths.parquet_path)

    store = DuckDBStore(paths.duckdb_path)
    store.create_tables(outputs)

    return outputs
