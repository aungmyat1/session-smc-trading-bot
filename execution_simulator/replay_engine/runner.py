from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Callable

from execution_simulator.broker.virtual_broker import VirtualBroker
from execution_simulator.replay_engine.market_feed import MarketFeed


@dataclass
class ReplayRunner:
    """Drive a market feed into a virtual broker and optional strategy hook."""

    feed: MarketFeed
    broker: VirtualBroker
    on_tick: Callable[[object, VirtualBroker], object] | None = None
    processed_ticks: int = 0
    errors: list[str] = field(default_factory=list)

    async def run(self) -> "ReplayRunner":
        await self.broker.connect()
        try:
            while True:
                tick = self.feed.get_tick()
                if tick is None:
                    break
                self.broker.on_market_event(tick)
                self.processed_ticks += 1

                if self.on_tick is None:
                    continue

                result = self.on_tick(tick, self.broker)
                if inspect.isawaitable(result):
                    await result
        except Exception as exc:
            self.errors.append(str(exc))
            raise
        return self

