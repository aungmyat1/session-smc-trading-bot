"""
SAFETY-01 — verifies bot.py's closed-position reconciliation actually feeds
real trade-close outcomes into RiskManager.record_trade_result(), so the
daily/weekly/monthly/consecutive-loss circuit breakers reflect reality.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from execution.metaapi_client import BrokerPosition
from execution.risk_manager import RiskManager
from execution.trade_logger import TradeLogger
from tests.test_ops01_safety import BASE_CONFIG

from bot import _process_closed_positions


def make_risk(tmp_path, monkeypatch, config=None) -> RiskManager:
    monkeypatch.setattr("execution.risk_manager.STATE_FILE", tmp_path / "bot_state.json")
    return RiskManager(config or BASE_CONFIG)


def make_client(open_positions: list) -> AsyncMock:
    client = AsyncMock()
    client.get_open_positions = AsyncMock(return_value=open_positions)
    return client


@pytest.mark.asyncio
async def test_no_positions_no_op(tmp_path, monkeypatch):
    risk = make_risk(tmp_path, monkeypatch)
    trade_logger = TradeLogger(tmp_path / "trades.jsonl")
    telegram = AsyncMock()
    client = make_client([])

    result = await _process_closed_positions(client, risk, trade_logger, telegram, BASE_CONFIG, {})

    assert result == {}
    telegram.send_trade_close.assert_not_called()


@pytest.mark.asyncio
async def test_open_position_seeds_snapshot_without_recording(tmp_path, monkeypatch):
    """First tick after (re)start: nothing was previously tracked, so a
    currently-open position must NOT be misread as a close."""
    risk = make_risk(tmp_path, monkeypatch)
    trade_logger = TradeLogger(tmp_path / "trades.jsonl")
    telegram = AsyncMock()
    pos = BrokerPosition("p1", "EURUSD", "long", 0.10, 1.1000, 1.0950, 1.1100, 5.0, 21001)
    client = make_client([pos])

    result = await _process_closed_positions(client, risk, trade_logger, telegram, BASE_CONFIG, {})

    assert result == {"p1": pos}
    telegram.send_trade_close.assert_not_called()
    assert risk.state.daily_loss_r == 0.0


@pytest.mark.asyncio
async def test_closed_losing_position_records_negative_r(tmp_path, monkeypatch):
    risk = make_risk(tmp_path, monkeypatch)
    trade_logger = TradeLogger(tmp_path / "trades.jsonl")
    telegram = AsyncMock()

    # open_price=1.1000, sl=1.0950 -> risk=50 pips; pip_value=10/lot; volume=0.10
    # risk_amount = 50 * 10 * 0.10 = $50. Loss of $50 -> result_r = -1.0
    pos = BrokerPosition("p1", "EURUSD", "long", 0.10, 1.1000, 1.0950, 1.1100, -50.0, 21001)
    last_positions = {"p1": pos}
    client = make_client([])  # position no longer open -> closed

    result = await _process_closed_positions(
        client, risk, trade_logger, telegram, BASE_CONFIG, last_positions,
    )

    assert result == {}
    assert risk.state.daily_loss_r == pytest.approx(1.0)
    assert risk.state.weekly_loss_r == pytest.approx(1.0)
    assert risk.state.monthly_loss_r == pytest.approx(1.0)
    telegram.send_trade_close.assert_awaited_once()
    events = trade_logger.read_all()
    assert events[-1]["event"] == "POSITION_CLOSED"
    assert events[-1]["result_r"] == pytest.approx(-1.0)


@pytest.mark.asyncio
async def test_halt_trip_sends_circuit_breaker_alert_once(tmp_path, monkeypatch):
    config = {
        "risk": {**BASE_CONFIG["risk"], "max_daily_loss_r": 0.5},
        "pip_value_per_lot": {"EURUSD": 10.0},
    }
    risk = make_risk(tmp_path, monkeypatch, config)
    trade_logger = TradeLogger(tmp_path / "trades.jsonl")
    telegram = AsyncMock()

    pos = BrokerPosition("p1", "EURUSD", "long", 0.10, 1.1000, 1.0950, 1.1100, -50.0, 21001)
    last_positions = {"p1": pos}
    client = make_client([])

    result = await _process_closed_positions(
        client, risk, trade_logger, telegram, config, last_positions,
    )

    assert risk.state.halted
    assert risk.state.halt_reason == "MAX_DAILY_LOSS"
    telegram.send_circuit_breaker.assert_awaited_once()
    assert result == {}


@pytest.mark.asyncio
async def test_broker_fetch_failure_preserves_last_positions(tmp_path, monkeypatch):
    risk = make_risk(tmp_path, monkeypatch)
    trade_logger = TradeLogger(tmp_path / "trades.jsonl")
    telegram = AsyncMock()
    pos = BrokerPosition("p1", "EURUSD", "long", 0.10, 1.1000, 1.0950, 1.1100, -50.0, 21001)
    last_positions = {"p1": pos}
    client = AsyncMock()
    client.get_open_positions = AsyncMock(side_effect=RuntimeError("rpc timeout"))

    result = await _process_closed_positions(
        client, risk, trade_logger, telegram, BASE_CONFIG, last_positions,
    )

    assert result == last_positions
    assert risk.state.daily_loss_r == 0.0
    telegram.send_trade_close.assert_not_called()
