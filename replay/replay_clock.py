from __future__ import annotations

from datetime import datetime
from typing import Sequence

from replay.replay_config import parse_timestamp


class ReplayClock:
    """Clock that advances only across a fixed sequence of candle timestamps."""

    def __init__(self, start_time: datetime, end_time: datetime, timestamps: Sequence[datetime]) -> None:
        self.start_time = parse_timestamp(start_time)
        self.end_time = parse_timestamp(end_time)
        if self.end_time < self.start_time:
            raise ValueError("end_time must not precede start_time")
        normalized = (parse_timestamp(item) for item in timestamps)
        self._timestamps = tuple(sorted(item for item in normalized if self.start_time <= item <= self.end_time))
        self._index = -1
        self.current_time = self.start_time

    def step(self) -> datetime | None:
        if self.is_finished():
            return None
        self._index += 1
        self.current_time = self._timestamps[self._index]
        return self.current_time

    def seek(self, timestamp: datetime) -> datetime:
        target = parse_timestamp(timestamp)
        if not self.start_time <= target <= self.end_time:
            raise ValueError("seek timestamp is outside the replay window")
        self._index = next((index - 1 for index, item in enumerate(self._timestamps) if item >= target), len(self._timestamps) - 1)
        self.current_time = target
        return self.current_time

    def reset(self) -> None:
        self._index = -1
        self.current_time = self.start_time

    def is_finished(self) -> bool:
        return self._index + 1 >= len(self._timestamps)
