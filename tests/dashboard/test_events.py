from __future__ import annotations

import asyncio
import json

from dashboard.events import (
    EventBroadcaster,
    EventPoller,
    make_strategy_event,
    make_system_event,
    make_trade_event,
)


def test_event_factories_tag_source_system_correctly():
    trade = make_trade_event("order_filled", strategy_id="ST-A2", session_id="s1", price=1.1)
    strategy = make_strategy_event("strategy_started", strategy_id="ST-A2", session_id="s1")
    system = make_system_event("broker_disconnected", severity="warning")

    assert trade.source_system == "execution"
    assert trade.payload["price"] == 1.1
    assert strategy.source_system == "strategy"
    assert system.source_system == "system"
    assert system.severity == "warning"
    assert trade.event_id and trade.timestamp


def test_broadcaster_fans_out_to_multiple_subscribers():
    async def run():
        broadcaster = EventBroadcaster()
        q1 = broadcaster.subscribe()
        q2 = broadcaster.subscribe()
        assert broadcaster.subscriber_count == 2

        broadcaster.publish(make_system_event("tick"))

        e1 = await asyncio.wait_for(q1.get(), timeout=1)
        e2 = await asyncio.wait_for(q2.get(), timeout=1)
        assert e1.event_type == "tick"
        assert e2.event_type == "tick"

        broadcaster.unsubscribe(q1)
        assert broadcaster.subscriber_count == 1

    asyncio.run(run())


def test_broadcaster_drops_oldest_on_full_queue_without_crashing():
    async def run():
        broadcaster = EventBroadcaster()
        q = broadcaster.subscribe()
        # Fill well past capacity; publish() must never raise.
        for i in range(600):
            broadcaster.publish(make_system_event(f"event-{i}"))
        assert q.qsize() <= 500

    asyncio.run(run())


def test_poller_deduplicates_operations_events(tmp_path, monkeypatch):
    rows = [
        {"created_at": "t1", "event_type": "intent_received", "type": "execution_event", "payload": {"strategy_id": "ST-A2"}},
    ]
    monkeypatch.setattr("execution.operations_recorder.get_recent_events", lambda limit=50: rows)
    broadcaster = EventBroadcaster()
    broadcaster.subscribe()
    poller = EventPoller(broadcaster)

    first_pass = poller._poll_operations_events()
    second_pass = poller._poll_operations_events()

    assert first_pass == 1
    assert second_pass == 0  # same row already seen, not re-published


def test_poller_reads_control_events(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "dashboard.control_state.load_control_state",
        lambda: {"control_events": [{"recorded_at": "t1", "action": "emergency_stop_activated", "actor": "op1", "detail": {}}]},
    )
    broadcaster = EventBroadcaster()
    poller = EventPoller(broadcaster)

    count = poller._poll_control_events()

    assert count == 1
    assert poller._poll_control_events() == 0


def test_poller_detects_broker_status_transition(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "logs").mkdir()
    state_path = tmp_path / "logs" / "strategy_demo_state.json"

    broadcaster = EventBroadcaster()
    q = broadcaster.subscribe()
    poller = EventPoller(broadcaster)

    state_path.write_text(json.dumps({"broker_status": "connected"}))
    assert poller._poll_broker_transition() == 0  # first read just primes last-known state

    state_path.write_text(json.dumps({"broker_status": "disconnected"}))
    assert poller._poll_broker_transition() == 1
    event = q.get_nowait()
    assert event.event_type == "broker_disconnected"
    assert event.severity == "warning"
