"""
Shared Broker Runtime (SYSTEM2_MASTER_PLAN.md Phase 1, 2026-07-06): the
dashboard no longer opens its own MetaAPI session to read account/positions/
market-watch/chart data — it reads the files scripts/run_st_a2_demo.py (the
deployed runner) already writes every tick. Replaces the old timeout/caching
test file (test_live_dashboard_timeout.py), which exclusively tested the
threaded RPC/caching mechanism this change removed.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import dashboard.live_dashboard_service as service


def _write_state(tmp_path, **overrides) -> None:
    state = {
        "broker_status": "connected",
        "last_tick_at": datetime.now(timezone.utc).isoformat(),
        "account": {"balance": 1000.0, "equity": 1000.0, "margin": 0.0, "free_margin": 1000.0, "currency": "USD"},
        "open_positions": [],
        "pair_results": [{"symbol": "EURUSD", "price": 1.1, "spread_pips": 1.2, "status": "ready"}],
        "strategy": "ST-A2",
        **overrides,
    }
    service.RUNNER_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    service.RUNNER_STATE_PATH.write_text(json.dumps(state), encoding="utf-8")


def test_snapshot_missing_state_file_reports_disconnected_honestly(tmp_path, monkeypatch):
    monkeypatch.setattr(service, "RUNNER_STATE_PATH", tmp_path / "does_not_exist.json")

    snapshot = service._fetch_broker_snapshot(["EURUSD"], "EURUSD", "M15", 120)

    assert snapshot["available"] is False
    assert snapshot["status"] == "DISCONNECTED"
    assert "not found" in snapshot["detail"]


def test_snapshot_corrupt_state_file_reports_disconnected_not_crash(tmp_path, monkeypatch):
    path = tmp_path / "strategy_demo_state.json"
    path.write_text("{not valid json", encoding="utf-8")
    monkeypatch.setattr(service, "RUNNER_STATE_PATH", path)

    snapshot = service._fetch_broker_snapshot(["EURUSD"], "EURUSD", "M15", 120)

    assert snapshot["available"] is False
    assert snapshot["status"] == "DISCONNECTED"
    assert "unreadable" in snapshot["detail"]


def test_snapshot_stale_heartbeat_reports_stale_not_fabricated_data(tmp_path, monkeypatch):
    monkeypatch.setattr(service, "RUNNER_STATE_PATH", tmp_path / "strategy_demo_state.json")
    stale_time = (datetime.now(timezone.utc) - timedelta(seconds=999)).isoformat()
    _write_state(tmp_path, last_tick_at=stale_time)

    snapshot = service._fetch_broker_snapshot(["EURUSD"], "EURUSD", "M15", 120)

    assert snapshot["available"] is False
    assert snapshot["status"] == "STALE"
    assert snapshot["stale"] is True
    assert snapshot["account"] == {}  # no fabricated account data behind a stale heartbeat


def test_snapshot_disconnected_broker_status_reports_degraded(tmp_path, monkeypatch):
    monkeypatch.setattr(service, "RUNNER_STATE_PATH", tmp_path / "strategy_demo_state.json")
    _write_state(tmp_path, broker_status="disconnected")

    snapshot = service._fetch_broker_snapshot(["EURUSD"], "EURUSD", "M15", 120)

    assert snapshot["available"] is False
    assert snapshot["status"] == "DEGRADED"


def test_snapshot_fresh_state_returns_real_account_and_positions(tmp_path, monkeypatch):
    monkeypatch.setattr(service, "RUNNER_STATE_PATH", tmp_path / "strategy_demo_state.json")
    monkeypatch.setattr(service, "RUNNER_CANDLES_DIR", tmp_path / "candles")
    _write_state(
        tmp_path,
        open_positions=[
            {"id": "P1", "symbol": "EURUSD", "direction": "long", "lots": 0.1, "entry": 1.1,
             "current_price": 1.105, "sl": 1.095, "tp": 1.12, "profit": 5.0, "magic": 21099},
        ],
    )

    snapshot = service._fetch_broker_snapshot(["EURUSD"], "EURUSD", "M15", 120)

    assert snapshot["available"] is True
    assert snapshot["status"] == "CONNECTED"
    assert snapshot["source"] == "runner_shared_state"
    assert snapshot["account"]["balance"] == 1000.0
    assert len(snapshot["positions"]) == 1
    pos = snapshot["positions"][0]
    assert pos["id"] == "P1"
    assert pos["volume"] == 0.1  # mapped from the runner's "lots" field
    assert pos["entry_price"] == 1.1  # mapped from the runner's "entry" field
    assert pos["stop_loss"] == 1.095  # mapped from the runner's "sl" field
    assert pos["strategy_name"] == "ST-A2"
    assert snapshot["orders"] == []  # market-order-only strategy, honestly empty


def test_snapshot_reads_candles_from_runner_written_file(tmp_path, monkeypatch):
    monkeypatch.setattr(service, "RUNNER_STATE_PATH", tmp_path / "strategy_demo_state.json")
    candles_dir = tmp_path / "candles"
    candles_dir.mkdir()
    (candles_dir / "EURUSD_M15.json").write_text(
        json.dumps([{"time": "2026-07-06T00:00:00+00:00", "open": 1.1, "high": 1.11, "low": 1.09, "close": 1.105, "volume": 10}]),
        encoding="utf-8",
    )
    monkeypatch.setattr(service, "RUNNER_CANDLES_DIR", candles_dir)
    _write_state(tmp_path)

    snapshot = service._fetch_broker_snapshot(["EURUSD"], "EURUSD", "M15", 120)

    assert len(snapshot["chart"]["candles"]) == 1
    assert snapshot["chart"]["candles"][0]["close"] == 1.105


def test_no_metaapi_connection_opened_for_a_snapshot_read(tmp_path, monkeypatch):
    """The whole point of this change: reading a snapshot must never
    instantiate a broker connection. Patch MT5Connector to raise if
    constructed — the snapshot call must still succeed."""
    monkeypatch.setattr(service, "RUNNER_STATE_PATH", tmp_path / "strategy_demo_state.json")
    monkeypatch.setattr(service, "RUNNER_CANDLES_DIR", tmp_path / "candles")
    _write_state(tmp_path)

    def _boom(*_a, **_kw):
        raise AssertionError("MT5Connector must not be constructed for a read-only snapshot")

    monkeypatch.setattr(service, "MT5Connector", _boom)

    snapshot = service._fetch_broker_snapshot(["EURUSD"], "EURUSD", "M15", 120)

    assert snapshot["available"] is True
