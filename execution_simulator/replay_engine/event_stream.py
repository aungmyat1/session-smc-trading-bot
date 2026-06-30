from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Iterator


@dataclass(frozen=True, slots=True)
class MarketEvent:
    timestamp: datetime
    symbol: str
    bid: float
    ask: float
    volume: float = 0.0

    def __post_init__(self) -> None:
        if self.timestamp.tzinfo is None:
            object.__setattr__(
                self, "timestamp", self.timestamp.replace(tzinfo=timezone.utc)
            )


class EventStream:
    """Sorted, single-pass stream of market events."""

    def __init__(self, events: Iterable[MarketEvent]) -> None:
        self._events = sorted(list(events), key=lambda ev: ev.timestamp)
        self._index = 0

    @classmethod
    def from_records(
        cls, rows: Iterable[dict], symbol: str | None = None
    ) -> "EventStream":
        events = []
        for row in rows:
            ts = row.get("timestamp") or row.get("timestamp_utc") or row.get("time")
            if isinstance(ts, str):
                ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if not isinstance(ts, datetime):
                raise TypeError(f"Unsupported timestamp value: {ts!r}")
            events.append(
                MarketEvent(
                    timestamp=ts,
                    symbol=symbol or str(row.get("symbol", "")),
                    bid=float(row["bid"]),
                    ask=float(row["ask"]),
                    volume=float(row.get("volume", 0.0)),
                )
            )
        return cls(events)

    def peek(self) -> MarketEvent | None:
        if self._index >= len(self._events):
            return None
        return self._events[self._index]

    def next(self) -> MarketEvent | None:
        event = self.peek()
        if event is not None:
            self._index += 1
        return event

    def reset(self) -> None:
        self._index = 0

    def __len__(self) -> int:
        return len(self._events)

    def __iter__(self) -> Iterator[MarketEvent]:
        while True:
            event = self.next()
            if event is None:
                return
            yield event
