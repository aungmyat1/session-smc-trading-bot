from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from execution_simulator.replay_engine.event_stream import MarketEvent


@dataclass(frozen=True, slots=True)
class FillResult:
    order_id: str
    symbol: str
    direction: str
    requested_price: float
    filled_price: float
    slippage: float
    latency_ms: int
    filled_at: datetime
    dry_run: bool = True


class FillEngine:
    """Simulate latency and slippage on top of the replay tick."""

    def __init__(
        self,
        latency_ms: int = 150,
        slippage_points: float = 0.3,
        point_size_by_symbol: dict[str, float] | None = None,
    ) -> None:
        self.latency_ms = latency_ms
        self.slippage_points = slippage_points
        self.point_size_by_symbol = point_size_by_symbol or {"EURUSD": 0.0001, "GBPUSD": 0.0001, "XAUUSD": 0.01}

    def fill_order(
        self,
        order_id: str,
        symbol: str,
        direction: str,
        market_event: MarketEvent,
    ) -> FillResult:
        point = self.point_size_by_symbol.get(symbol, 0.0001)
        slippage = self.slippage_points * point
        if direction.lower() in {"long", "buy"}:
            requested_price = market_event.ask
            filled_price = requested_price + slippage
        else:
            requested_price = market_event.bid
            filled_price = requested_price - slippage
        filled_at = market_event.timestamp + timedelta(milliseconds=self.latency_ms)
        return FillResult(
            order_id=order_id,
            symbol=symbol,
            direction=direction,
            requested_price=requested_price,
            filled_price=filled_price,
            slippage=abs(filled_price - requested_price),
            latency_ms=self.latency_ms,
            filled_at=filled_at,
        )

