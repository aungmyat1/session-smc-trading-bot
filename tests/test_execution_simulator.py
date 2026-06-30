from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from execution_simulator import (
    ExecutionLog,
    EventStream,
    MarketEvent,
    MarketFeed,
    ReplayClock,
    VirtualBroker,
)
from execution_simulator.broker.virtual_broker import VirtualBrokerConfig

UTC = timezone.utc


def _event(
    offset_minutes: int, bid: float, ask: float, symbol: str = "EURUSD"
) -> MarketEvent:
    return MarketEvent(
        timestamp=datetime(2026, 6, 27, 8, 0, tzinfo=UTC)
        + timedelta(minutes=offset_minutes),
        symbol=symbol,
        bid=bid,
        ask=ask,
        volume=100.0,
    )


def test_replay_clock_scales_time():
    clock = ReplayClock(replay_speed=100.0)
    start = datetime(2026, 6, 27, 8, 0, tzinfo=UTC)
    later = start + timedelta(seconds=100)
    clock.attach(start, wall_time=start)
    assert clock.wall_elapsed(later) == timedelta(seconds=1)


def test_market_feed_returns_events_in_order():
    feed = MarketFeed(EventStream([_event(1, 1.1, 1.1002), _event(0, 1.0, 1.0002)]))
    first = feed.get_tick()
    second = feed.get_tick()
    assert first is not None and first.timestamp < second.timestamp
    assert feed.get_tick() is None


@pytest.mark.asyncio
async def test_virtual_broker_places_and_closes_order(tmp_path, monkeypatch):
    log = ExecutionLog(tmp_path / "execution.sqlite3")
    feed = MarketFeed(
        EventStream([_event(0, 1.0999, 1.1001), _event(1, 1.1002, 1.1004)])
    )
    broker = VirtualBroker(
        feed=feed,
        config=VirtualBrokerConfig(balance=1_000.0, max_spread_pips={"EURUSD": 5.0}),
        execution_log=log,
    )

    await broker.connect()
    tick = feed.get_tick()
    assert tick is not None
    broker.on_market_event(tick)
    result = await broker.place_order(
        symbol="EURUSD",
        direction="long",
        volume=0.01,
        sl=1.0900,
        tp=1.1200,
        magic=21001,
        comment="test",
    )
    assert result.order_id.startswith("VIRT-ORD-")

    positions = await broker.get_open_positions(magic=21001)
    assert len(positions) == 1

    next_tick = feed.get_tick()
    assert next_tick is not None
    broker.on_market_event(next_tick)
    assert await broker.close_position(
        broker._positions.open_positions()[0].position_id, reason="TEST"
    )
    summary = broker.execution_summary()
    assert summary["orders"] == 1
    assert summary["positions"] == 1
    event_types = [event.event_type for event in broker.execution_events()]
    assert event_types[:4] == [
        "ORDER_RECEIVED",
        "ORDER_VALIDATED",
        "ORDER_FILLED",
        "POSITION_OPENED",
    ]
    assert "POSITION_CLOSED" in event_types


def test_execution_log_records_comparisons(tmp_path):
    log = ExecutionLog(tmp_path / "execution.sqlite3")
    log.log_order(
        order_id="1",
        symbol="EURUSD",
        direction="long",
        requested_price=1.1,
        filled_price=1.1003,
        slippage=0.0003,
        latency_ms=150,
        status="filled",
    )
    log.log_signal_comparison(
        symbol="EURUSD",
        expected_direction="long",
        actual_direction="long",
        expected_entry=1.1,
        actual_entry=1.1003,
        slippage=0.0003,
        latency_ms=150,
        verdict="PASS",
    )
    assert log.summary() == {
        "orders": 1,
        "positions": 0,
        "fills": 0,
        "signal_comparison": 1,
    }
    assert len(log.fetch("orders")) == 1
