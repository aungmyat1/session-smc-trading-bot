from __future__ import annotations

import pytest

import scripts.reconcile_positions as reconcile_positions


@pytest.mark.asyncio
async def test_reconcile_positions_reports_in_sync(monkeypatch):
    class _Connector:
        async def connect(self):
            return None

        async def disconnect(self):
            return None

    class _Executor:
        def __init__(self, connector):
            self.connector = connector

        async def get_positions(self):
            return [{"symbol": "EURUSD", "id": "ORD-1", "direction": "buy", "magic": reconcile_positions._MAGIC}]

    class _DB:
        def get_open_trades(self):
            return [{"symbol": "EURUSD", "broker_order_id": "ORD-1", "direction": "long"}]

    monkeypatch.setattr(reconcile_positions, "MT5Connector", lambda mode="demo": _Connector())
    monkeypatch.setattr(reconcile_positions, "VantageDemoExecutor", _Executor)
    monkeypatch.setattr(reconcile_positions, "TradeJournalDB", lambda: _DB())

    code = await reconcile_positions.run(dry_run=True)

    assert code == 0


@pytest.mark.asyncio
async def test_reconcile_positions_detects_mismatch(monkeypatch):
    class _Connector:
        async def connect(self):
            return None

        async def disconnect(self):
            return None

    class _Executor:
        def __init__(self, connector):
            self.connector = connector

        async def get_positions(self):
            return [{"symbol": "EURUSD", "id": "ORD-2", "direction": "buy", "magic": reconcile_positions._MAGIC}]

    class _DB:
        def get_open_trades(self):
            return [{"symbol": "EURUSD", "broker_order_id": "ORD-1", "direction": "long"}]

    monkeypatch.setattr(reconcile_positions, "MT5Connector", lambda mode="demo": _Connector())
    monkeypatch.setattr(reconcile_positions, "VantageDemoExecutor", _Executor)
    monkeypatch.setattr(reconcile_positions, "TradeJournalDB", lambda: _DB())

    code = await reconcile_positions.run(dry_run=True)

    assert code == 1

