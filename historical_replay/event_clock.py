from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class EventClock:
    now: datetime | None = None

    def advance(self, timestamp: datetime) -> datetime:
        if self.now is not None and timestamp <= self.now:
            raise ValueError("replay clock must advance strictly")
        self.now = timestamp
        return timestamp
