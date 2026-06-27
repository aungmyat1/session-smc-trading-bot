from __future__ import annotations

from datetime import datetime, timezone

import pytest

from core.broker_interface import BrokerInterface
from execution_gate import ExecutionGate, ExecutionGateConfig
from execution_simulator import EventStream, MarketEvent, MarketFeed, VirtualBroker
from execution_simulator.broker.virtual_broker import VirtualBrokerConfig
from execution_simulator.execution.risk_engine import RiskEngine
from models.order import Order
from virtual_broker import AccountManager, OrderValidator


def _tick() -> MarketEvent:
    return MarketEvent(
        timestamp=datetime(2026, 6, 27, 9, 30, tzinfo=timezone.utc),
        symbol="EURUSD",
        bid=1.1000,
        ask=1.1002,
        volume=100.0,
    )


def test_virtual_broker_matches_interface_contract():
    broker = VirtualBroker(
        feed=MarketFeed(EventStream([_tick()])),
        config=VirtualBrokerConfig(max_spread_pips={"EURUSD": 5.0}),
    )
    assert isinstance(broker, BrokerInterface)


@pytest.mark.asyncio
async def test_virtual_broker_alias_methods_work():
    broker = VirtualBroker(
        feed=MarketFeed(EventStream([_tick()])),
        config=VirtualBrokerConfig(max_spread_pips={"EURUSD": 5.0}),
    )
    await broker.connect()
    broker.on_market_event(_tick())
    account = await broker.get_account()
    price = await broker.get_price("EURUSD")
    assert account.balance == 10_000.0
    assert price.ask == pytest.approx(1.1002)


def test_execution_gate_approves_good_metrics():
    gate = ExecutionGate(ExecutionGateConfig())
    result = gate.evaluate(
        total_signals=100,
        total_orders=100,
        average_slippage_pip=0.1,
        maximum_slippage_pip=0.3,
        backtest_pf=1.50,
        virtual_pf=1.45,
    )
    assert result.approved is True
    assert result.status == "APPROVED FOR DEMO"


def test_execution_gate_rejects_large_pf_gap():
    gate = ExecutionGate(ExecutionGateConfig(maximum_pf_difference=0.05))
    result = gate.evaluate(
        total_signals=100,
        total_orders=96,
        average_slippage_pip=0.1,
        maximum_slippage_pip=0.3,
        backtest_pf=1.50,
        virtual_pf=1.20,
    )
    assert result.approved is False
    assert any("PF difference" in detail for detail in result.details)


def test_execution_model_and_wrappers_are_importable():
    order = Order(
        id="o-1",
        symbol="XAUUSD",
        direction="BUY",
        volume=0.2,
        entry_price=2328.55,
        stop_loss=2325.55,
        take_profit=2335.55,
        strategy_id="st-a2",
    )
    assert order.symbol == "XAUUSD"

    account = AccountManager()
    account.apply_margin(125.0)
    assert account.free_margin == pytest.approx(9875.0)

    validator = OrderValidator(risk_engine=RiskEngine())
    assert validator.risk_engine is not None
