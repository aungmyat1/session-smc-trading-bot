from __future__ import annotations

import sys
import types
from unittest.mock import AsyncMock

import pytest

sys.modules.setdefault("smartmoneyconcepts", types.SimpleNamespace(smc=object()))
import scripts.run_st_a2_demo as runner


class _Connector:
    reconnect_attempts_total = 2
    last_reconnect_at = "2026-07-01T00:00:00+00:00"
    is_connected = True


@pytest.mark.asyncio
async def test_tick_closes_positions_once_per_emergency_activation(monkeypatch):
    monkeypatch.setattr(
        runner,
        "load_control_state",
        lambda: {
            "emergency_stop": {
                "active": True,
                "activated_at": "2026-07-01T10:00:00+00:00",
                "reason": "manual pause",
            }
        },
    )
    manager = type(
        "Manager",
        (),
        {
            "emergency_close_all": AsyncMock(return_value=2),
            "get_positions": AsyncMock(return_value=[{"id": "POS-1"}]),
        },
    )()
    executor = type("Executor", (), {"get_account_info": AsyncMock(return_value={"balance": 1000.0})})()
    telegram = type("Telegram", (), {"send_emergency_stop": AsyncMock()})()
    risk_state = {"_dashboard_state": runner._base_state("shadow", "ST-A2", 60, once=True)}

    await runner._tick("shadow", "ST-A2", _Connector(), executor, manager, object(), risk_state, telegram)
    await runner._tick("shadow", "ST-A2", _Connector(), executor, manager, object(), risk_state, telegram)

    assert manager.emergency_close_all.await_count == 1
    assert telegram.send_emergency_stop.await_count == 1
    assert risk_state["_dashboard_state"]["last_decision"] == "emergency_stop_active"
