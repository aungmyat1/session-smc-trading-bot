from __future__ import annotations

import asyncio

import dashboard.live_dashboard_service as service


def _successful_snapshot() -> dict:
    return {
        "available": True,
        "status": "CONNECTED",
        "detail": "connected",
        "account": {"balance": 1000},
        "positions": [{"id": "position-1"}],
        "orders": [],
        "market_watch": [],
        "chart": {"symbol": "EURUSD", "timeframe": "M15", "candles": []},
        "heartbeat": {"connected": True, "latency_ms": 10, "last_heartbeat": "now"},
    }


def test_broker_snapshot_times_out_with_degraded_empty_payload(monkeypatch):
    async def stalled(*_args, **_kwargs):
        await asyncio.sleep(1)

    monkeypatch.setattr(service, "_fetch_broker_snapshot_async", stalled)
    monkeypatch.setattr(service, "SNAPSHOT_TIMEOUT_S", 0.01)
    monkeypatch.setattr(service, "_last_good_broker_snapshot", None)
    monkeypatch.setattr(service, "_broker_refresh", None)

    snapshot = service._fetch_broker_snapshot(["EURUSD"], "EURUSD", "M15", 120)

    assert snapshot["available"] is False
    assert snapshot["status"] == "DISCONNECTED"
    assert "deadline" in snapshot["detail"]


def test_broker_snapshot_uses_stale_cache_after_timeout(monkeypatch):
    async def successful(*_args, **_kwargs):
        return _successful_snapshot()

    async def stalled(*_args, **_kwargs):
        await asyncio.sleep(1)

    monkeypatch.setattr(service, "_fetch_broker_snapshot_async", successful)
    monkeypatch.setattr(service, "_last_good_broker_snapshot", None)
    monkeypatch.setattr(service, "_broker_refresh", None)
    first = service._fetch_broker_snapshot(["EURUSD"], "EURUSD", "M15", 120)
    assert first["stale"] is False

    monkeypatch.setattr(service, "_fetch_broker_snapshot_async", stalled)
    monkeypatch.setattr(service, "SNAPSHOT_TIMEOUT_S", 0.01)
    second = service._fetch_broker_snapshot(["EURUSD"], "EURUSD", "M15", 120)

    assert second["available"] is False
    assert second["status"] == "DEGRADED"
    assert second["stale"] is True
    assert second["account"]["balance"] == 1000
    assert "last successful snapshot" in second["detail"]
