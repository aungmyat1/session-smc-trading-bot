from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Callable

import pandas as pd

from historical_replay.event_clock import EventClock


@dataclass(frozen=True, slots=True)
class ReplayEvent:
    timestamp: str
    session: str | None
    signal: dict[str, Any]


@dataclass(slots=True)
class ReplayResult:
    run_id: str
    pair: str
    start: str
    end: str
    candles_processed: int
    events: list[ReplayEvent] = field(default_factory=list)
    missing_m1_candles: int = 0

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["events"] = [asdict(event) for event in self.events]
        return payload


SignalFunction = Callable[[pd.DataFrame], dict[str, Any] | list[dict[str, Any]] | None]


def session_at(timestamp: pd.Timestamp) -> str | None:
    """UTC labels are deterministic; DST-aware strategy rules may refine these."""
    hour = timestamp.hour
    if 7 <= hour < 12:
        return "London"
    if 13 <= hour < 17:
        return "New York"
    return None


class ReplayEngine:
    def __init__(self, pair: str, candles: pd.DataFrame, strategy: SignalFunction) -> None:
        self.pair = pair.upper().replace("/", "")
        self.candles = candles.reset_index(drop=True).copy()
        self.strategy = strategy

    def run(self) -> ReplayResult:
        if self.candles.empty:
            raise ValueError("replay requires at least one candle")
        clock = EventClock()
        events: list[ReplayEvent] = []
        seen: set[str] = set()
        # The callback receives only [0:i], making future-candle access impossible.
        for index in range(len(self.candles)):
            visible = self.candles.iloc[: index + 1].copy()
            timestamp = pd.Timestamp(visible.iloc[-1]["timestamp"])
            clock.advance(timestamp.to_pydatetime())
            emitted = self.strategy(visible)
            signals = emitted if isinstance(emitted, list) else ([] if emitted is None else [emitted])
            for signal in signals:
                canonical = json.dumps(signal, sort_keys=True, default=str)
                key = f"{timestamp.isoformat()}:{canonical}"
                if key in seen:
                    continue
                seen.add(key)
                events.append(ReplayEvent(timestamp.isoformat(), session_at(timestamp), signal))
        timestamps = pd.DatetimeIndex(self.candles["timestamp"])
        expected = int((timestamps[-1] - timestamps[0]).total_seconds() // 60) + 1
        run_payload = {
            "pair": self.pair,
            "start": timestamps[0].isoformat(),
            "end": timestamps[-1].isoformat(),
            "candles": self.candles.to_json(date_format="iso", orient="records"),
            "events": [asdict(event) for event in events],
        }
        run_id = hashlib.sha256(json.dumps(run_payload, sort_keys=True).encode()).hexdigest()[:20]
        return ReplayResult(run_id, self.pair, timestamps[0].isoformat(), timestamps[-1].isoformat(), len(self.candles), events, max(0, expected - len(timestamps)))
