from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

import pandas as pd

from replay.replay_config import parse_timestamp

REQUIRED_CANDLE_FIELDS = frozenset(
    {"symbol", "timestamp", "open", "high", "low", "close", "volume", "timeframe", "source"}
)


@dataclass(frozen=True, slots=True)
class HistoricalBar:
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    timeframe: str
    source: str

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["timestamp"] = self.timestamp.isoformat()
        return result


class HistoricalFeed:
    def __init__(self, data_path: str | Path) -> None:
        self.data_path = Path(data_path)
        frame = self._read(self.data_path)
        self.validate_schema(frame)
        self._bars = self._to_bars(frame)
        self._index = 0

    @staticmethod
    def _read(path: Path) -> pd.DataFrame:
        suffix = path.suffix.lower()
        if suffix == ".csv":
            return pd.read_csv(path)
        if suffix in {".parquet", ".pq"}:
            return pd.read_parquet(path)
        raise ValueError(f"unsupported historical data format: {suffix or '<none>'}")

    @staticmethod
    def validate_schema(frame: pd.DataFrame) -> None:
        missing = sorted(REQUIRED_CANDLE_FIELDS.difference(frame.columns))
        if missing:
            raise ValueError(f"historical data is missing required fields: {', '.join(missing)}")
        if frame[list(REQUIRED_CANDLE_FIELDS)].isnull().any().any():
            raise ValueError("historical data contains null required fields")

    @staticmethod
    def _to_bars(frame: pd.DataFrame) -> tuple[HistoricalBar, ...]:
        records: list[HistoricalBar] = []
        for row in frame.to_dict(orient="records"):
            records.append(
                HistoricalBar(
                    symbol=str(row["symbol"]).upper().replace("/", ""),
                    timestamp=parse_timestamp(str(row["timestamp"])),
                    open=float(row["open"]), high=float(row["high"]), low=float(row["low"]), close=float(row["close"]),
                    volume=float(row["volume"]), timeframe=str(row["timeframe"]).upper(), source=str(row["source"]),
                )
            )
        return tuple(sorted(records, key=lambda bar: bar.timestamp))

    @property
    def bars(self) -> tuple[HistoricalBar, ...]:
        return self._bars

    def get_next_bar(self) -> HistoricalBar | None:
        if self._index >= len(self._bars):
            return None
        bar = self._bars[self._index]
        self._index += 1
        return bar

    def get_bar_at(self, timestamp: datetime) -> HistoricalBar | None:
        target = parse_timestamp(timestamp)
        return next((bar for bar in self._bars if bar.timestamp == target), None)

    def stream_between(self, start: datetime, end: datetime) -> Iterator[HistoricalBar]:
        lower, upper = parse_timestamp(start), parse_timestamp(end)
        if upper < lower:
            raise ValueError("stream end must not precede start")
        return (bar for bar in self._bars if lower <= bar.timestamp <= upper)
