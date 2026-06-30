from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone


@dataclass
class ReplayClock:
    """Translate historical timestamps into accelerated replay time."""

    replay_speed: float = 100.0
    origin_replay_time: datetime | None = None
    origin_wall_time: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    current_replay_time: datetime | None = None

    def attach(self, replay_time: datetime, wall_time: datetime | None = None) -> None:
        if replay_time.tzinfo is None:
            replay_time = replay_time.replace(tzinfo=timezone.utc)
        self.origin_replay_time = replay_time
        self.current_replay_time = replay_time
        self.origin_wall_time = wall_time or datetime.now(timezone.utc)

    def advance_to(self, replay_time: datetime) -> None:
        if replay_time.tzinfo is None:
            replay_time = replay_time.replace(tzinfo=timezone.utc)
        if self.origin_replay_time is None:
            self.attach(replay_time)
            return
        self.current_replay_time = replay_time

    def wall_elapsed(self, replay_time: datetime) -> timedelta:
        if self.origin_replay_time is None:
            self.attach(replay_time)
        assert self.origin_replay_time is not None
        delta = replay_time - self.origin_replay_time
        return timedelta(seconds=delta.total_seconds() / max(self.replay_speed, 1e-9))

    def wall_time_for(self, replay_time: datetime) -> datetime:
        return self.origin_wall_time + self.wall_elapsed(replay_time)

    async def sleep_until(self, replay_time: datetime) -> None:
        target_wall = self.wall_time_for(replay_time)
        delay = (target_wall - datetime.now(timezone.utc)).total_seconds()
        if delay > 0:
            await asyncio.sleep(delay)
