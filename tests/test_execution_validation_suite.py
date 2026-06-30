from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from execution_validation import ExecutionValidationSuite, load_validation_rules
from execution_simulator.broker.virtual_broker import VirtualBroker, VirtualBrokerConfig
from execution_simulator.replay_engine.event_stream import MarketEvent
from models.order import Order

UTC = timezone.utc


def _tick(
    offset_minutes: int, bid: float, ask: float, symbol: str = "EURUSD"
) -> MarketEvent:
    return MarketEvent(
        timestamp=datetime(2026, 6, 27, 9, 30, tzinfo=UTC)
        + timedelta(minutes=offset_minutes),
        symbol=symbol,
        bid=bid,
        ask=ask,
        volume=100.0,
    )


@pytest.mark.asyncio
async def test_execution_validation_suite_runs_ready_for_demo(tmp_path):
    broker = VirtualBroker(
        config=VirtualBrokerConfig(
            balance=10_000.0,
            max_spread_pips={"EURUSD": 3.0},
            point_size_by_symbol={"EURUSD": 0.0001},
            slippage_points=0.3,
        ),
    )
    await broker.connect()

    entry_tick = _tick(0, 1.1000, 1.1001)
    broker.on_market_event(entry_tick)
    result = await broker.place_order(
        symbol="EURUSD",
        direction="long",
        volume=0.01,
        sl=1.0940,
        tp=1.1060,
        magic=21001,
        comment="suite",
        signal_timestamp=entry_tick.timestamp,
        expected_entry=1.1001,
    )
    snapshot = broker.snapshot_state()
    hit_tick = _tick(1, 1.1060, 1.1061)
    broker.on_market_event(hit_tick)

    orders = broker._orders.all()
    signals = [
        Order(
            id=result.order_id,
            symbol="EURUSD",
            direction="long",
            order_type="MARKET",
            volume=0.01,
            entry_price=1.1001,
            stop_loss=1.0940,
            take_profit=1.1060,
            timestamp=entry_tick.timestamp,
            strategy_id="ST-A2",
        )
    ]
    fills = orders
    events = broker.execution_events()
    risk_samples = [
        {
            "symbol": "EURUSD",
            "direction": "long",
            "volume": 0.01,
            "stop_loss": 1.0940,
            "take_profit": 1.1060,
            "market_event": entry_tick,
            "expected_allowed": True,
            "account_balance": 10_000.0,
        }
    ]
    broker_rule_samples = [
        {
            "symbol": "EURUSD",
            "direction": "long",
            "volume": 0.01,
            "stop_loss": 1.0940,
            "take_profit": 1.1060,
            "market_event": entry_tick,
            "expected_allowed": True,
            "account_balance": 10_000.0,
        },
        {
            "symbol": "EURUSD",
            "direction": "long",
            "volume": 0.01,
            "stop_loss": 1.0940,
            "take_profit": 1.1060,
            "market_event": _tick(0, 1.1000, 1.1010),
            "expected_allowed": False,
            "account_balance": 10_000.0,
        },
    ]

    suite = ExecutionValidationSuite(rules=load_validation_rules(), report_dir=tmp_path)
    report = suite.run(
        strategy="ST-A2",
        period="2026-06-27",
        signals=signals,
        orders=orders,
        fills=fills,
        execution_events=events,
        risk_samples=risk_samples,
        broker_rule_samples=broker_rule_samples,
        recovery_snapshot=snapshot,
        recovery_expected_open_positions=1,
        broker=broker,
        backtest_pf=1.5,
        virtual_pf=1.45,
    )

    assert report.status == "READY FOR DEMO"
    assert report.signal_accuracy == pytest.approx(1.0)
    assert report.order_accuracy == pytest.approx(1.0)
    assert report.risk_accuracy == pytest.approx(1.0)
    assert report.recovery_passed is True
    assert report.broker_simulation_passed is True
    assert report.final_score >= 90
    assert (tmp_path / "validation_report.json").exists()
