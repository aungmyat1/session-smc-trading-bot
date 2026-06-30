from __future__ import annotations

from dataclasses import dataclass

from execution_simulator.replay_engine.clock import ReplayClock
from execution_simulator.replay_engine.event_stream import EventStream, MarketEvent


@dataclass
class MarketFeed:
    """Broker-shaped market feed backed by historical replay events."""

    stream: EventStream
    clock: ReplayClock | None = None

    def __post_init__(self) -> None:
        self._last_tick: MarketEvent | None = None
        first_event = self.stream.peek()
        if self.clock is not None and first_event is not None:
            self.clock.attach(first_event.timestamp)

    def get_tick(self) -> MarketEvent | None:
        tick = self.stream.next()
        if tick is None:
            return None
        self._last_tick = tick
        if self.clock is not None:
            self.clock.advance_to(tick.timestamp)
        return tick

    @property
    def last_tick(self) -> MarketEvent | None:
        return self._last_tick

    @classmethod
    def from_records(
        cls,
        rows: list[dict],
        symbol: str | None = None,
        replay_speed: float = 100.0,
    ) -> "MarketFeed":
        return cls(
            EventStream.from_records(rows, symbol=symbol),
            ReplayClock(replay_speed=replay_speed),
        )
