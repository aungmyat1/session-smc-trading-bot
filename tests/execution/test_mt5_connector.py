from __future__ import annotations

import json

import pytest

from execution import mt5_connector
from execution.mt5_connector import MT5Connector


class _Conn:
    async def get_account_information(self):
        return {"balance": 1000}


@pytest.mark.asyncio
async def test_heartbeat_appends_latency_sample(tmp_path, monkeypatch):
    monkeypatch.setattr(mt5_connector, "_LATENCY_PATH", tmp_path / "latency_timeseries.jsonl")
    connector = MT5Connector()
    connector._connection = _Conn()

    payload = await connector.heartbeat()

    assert payload["connected"] is True
    lines = (tmp_path / "latency_timeseries.jsonl").read_text(encoding="utf-8").splitlines()
    sample = json.loads(lines[-1])
    assert sample["connected"] is True
    assert "latency_ms" in sample


@pytest.mark.asyncio
async def test_reconnect_increments_counter(monkeypatch):
    monkeypatch.setattr(mt5_connector, "_RECONNECT_DELAY_S", 0)
    connector = MT5Connector()

    async def _disconnect():
        return None

    async def _connect():
        return None

    connector.disconnect = _disconnect  # type: ignore[method-assign]
    connector.connect = _connect  # type: ignore[method-assign]

    await connector.reconnect()
    await connector.reconnect()

    assert connector.reconnect_attempts_total == 2
    assert connector.last_reconnect_at

