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


@pytest.mark.asyncio
async def test_tick_blocks_from_the_very_first_tick_when_already_active_at_startup(monkeypatch):
    """Emergency stop active at startup — before this process ever ran a
    tick — must still block on tick #1, not only on a subsequent tick."""
    monkeypatch.setattr(
        runner,
        "load_control_state",
        lambda: {
            "emergency_stop": {
                "active": True,
                "activated_at": "2026-07-05T09:00:00+00:00",
                "reason": "pre-existing stop from a prior session",
            }
        },
    )
    manager = type(
        "Manager",
        (),
        {
            "emergency_close_all": AsyncMock(return_value=0),
            "get_positions": AsyncMock(return_value=[]),
        },
    )()
    executor = type("Executor", (), {"get_account_info": AsyncMock(return_value={"balance": 1000.0})})()
    risk_state = {"_dashboard_state": runner._base_state("shadow", "ST-A2", 60, once=True)}

    result = await runner._tick("shadow", "ST-A2", _Connector(), executor, manager, object(), risk_state, None)

    assert manager.emergency_close_all.await_count == 1
    assert result["_dashboard_state"]["status"] == "blocked"
    assert result["_dashboard_state"]["last_decision"] == "emergency_stop_active"


@pytest.mark.asyncio
async def test_tick_resumes_normal_processing_after_emergency_stop_cleared(monkeypatch):
    """Once the stop is cleared, the next tick must reach normal processing
    again, not remain stuck reporting emergency_stop_active."""
    control_state = {
        "emergency_stop": {"active": True, "activated_at": "2026-07-05T09:00:00+00:00", "reason": "manual pause"}
    }
    monkeypatch.setattr(runner, "load_control_state", lambda: control_state)
    manager = type(
        "Manager",
        (),
        {
            "emergency_close_all": AsyncMock(return_value=1),
            "get_positions": AsyncMock(return_value=[]),
        },
    )()
    executor = type("Executor", (), {"get_account_info": AsyncMock(return_value={"balance": 1000.0})})()
    risk_state = {"_dashboard_state": runner._base_state("shadow", "ST-A2", 60, once=True)}

    await runner._tick("shadow", "ST-A2", _Connector(), executor, manager, object(), risk_state, None)
    assert risk_state["_dashboard_state"]["last_decision"] == "emergency_stop_active"

    # Clear it, then rig the very next check after the emergency-stop block
    # (the portfolio loss guard) to short-circuit — proving the tick reached
    # past the emergency-stop path entirely, not just re-checked it.
    control_state["emergency_stop"] = {"active": False}
    monkeypatch.setattr(runner._portmgr, "any_loss_limit_hit", lambda: True)
    monkeypatch.setattr(runner._portmgr, "stats", lambda: {})

    result = await runner._tick("shadow", "ST-A2", _Connector(), executor, manager, object(), risk_state, None)

    assert result["_dashboard_state"]["last_decision"] == "portfolio_loss_limit"
    assert result.get("_emergency_stop_handled_at", "") == ""


@pytest.mark.asyncio
async def test_tick_degrades_gracefully_when_broker_disconnected_during_emergency_stop(monkeypatch):
    """A disconnected broker while the emergency stop is active must not
    crash the tick — it should keep reporting blocked status with empty/best-
    effort broker data instead."""
    monkeypatch.setattr(
        runner,
        "load_control_state",
        lambda: {"emergency_stop": {"active": True, "activated_at": "2026-07-05T09:00:00+00:00", "reason": "manual pause"}},
    )
    manager = type(
        "Manager",
        (),
        {
            "emergency_close_all": AsyncMock(return_value=0),
            "get_positions": AsyncMock(side_effect=ConnectionError("broker disconnected")),
        },
    )()
    executor = type("Executor", (), {"get_account_info": AsyncMock(side_effect=ConnectionError("broker disconnected"))})()
    risk_state = {"_dashboard_state": runner._base_state("shadow", "ST-A2", 60, once=True)}

    result = await runner._tick("shadow", "ST-A2", _Connector(), executor, manager, object(), risk_state, None)

    assert result["_dashboard_state"]["status"] == "blocked"
    assert result["_dashboard_state"]["open_positions"] == []
    # get_account_info() raised — the try/except leaves the pre-existing
    # default ({}) rather than fabricating a value or crashing the tick.
    assert result["_dashboard_state"]["account"] == {}


@pytest.mark.asyncio
async def test_tick_logs_structured_reason_while_paused(monkeypatch, caplog):
    monkeypatch.setattr(
        runner,
        "load_control_state",
        lambda: {
            "emergency_stop": {
                "active": True,
                "activated_at": "2026-07-05T09:00:00+00:00",
                "reason": "manual pause",
                "source": "control_pause",
            }
        },
    )
    manager = type(
        "Manager",
        (),
        {"emergency_close_all": AsyncMock(return_value=0), "get_positions": AsyncMock(return_value=[])},
    )()
    executor = type("Executor", (), {"get_account_info": AsyncMock(return_value={"balance": 1000.0})})()
    risk_state = {"_dashboard_state": runner._base_state("shadow", "ST-A2", 60, once=True)}

    with caplog.at_level("INFO", logger="strategy_demo.runner"):
        await runner._tick("shadow", "ST-A2", _Connector(), executor, manager, object(), risk_state, None)

    paused_logs = [m for m in caplog.messages if "Trading paused" in m]
    assert paused_logs, "expected a structured 'Trading paused' log entry"
    assert "manual pause" in paused_logs[0]
    assert "control_pause" in paused_logs[0]
