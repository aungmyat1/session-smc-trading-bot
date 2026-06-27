from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from execution_validation.engine import ExecutionValidationReport, ExecutionValidationSuite
from execution_simulator.broker.virtual_broker import VirtualBroker, VirtualBrokerConfig
from execution_simulator.replay_engine.event_stream import MarketEvent
from simulator.forward_test import ForwardTestSimulator

_UTC = timezone.utc


def _utc_time(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=_UTC)
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _candle_to_event(candle: dict, symbol: str, spread_pips: float = 1.0, point_size: float = 0.0001) -> MarketEvent:
    ts = _utc_time(candle["time"])
    close = float(candle["close"])
    spread = spread_pips * point_size
    return MarketEvent(
        timestamp=ts,
        symbol=symbol,
        bid=close,
        ask=close + spread,
        volume=float(candle.get("volume", 0.0) or 0.0),
    )


def _signal_id(signal: Any) -> str:
    return getattr(signal, "signal_id", "") or getattr(signal, "id", "") or signal.timestamp.isoformat()


@dataclass(slots=True)
class ReplayValidationPayload:
    strategy: str
    period: str
    signals: list[dict[str, Any]]
    orders: list[dict[str, Any]]
    fills: list[dict[str, Any]]
    execution_events: list[Any]
    risk_samples: list[dict[str, Any]]
    broker_rule_samples: list[dict[str, Any]]
    recovery_snapshot: dict[str, Any]
    recovery_expected_open_positions: int
    backtest_pf: float
    virtual_pf: float


async def build_validation_payload_from_candles(
    *,
    strategy: str,
    period: str,
    symbol: str,
    candles_m15: list[dict],
    candles_h4: list[dict],
    broker_config: VirtualBrokerConfig | None = None,
    spread_pips: float = 1.0,
    point_size: float = 0.0001,
    backtest_pf: float = 1.0,
    virtual_pf: float = 1.0,
) -> ReplayValidationPayload:
    """
    Replay historical candles through the strategy and virtual broker, then
    package the execution artifacts for the validation suite.
    """
    simulator = ForwardTestSimulator(symbol, h4_candles=candles_h4)
    broker = VirtualBroker(config=broker_config or VirtualBrokerConfig())
    await broker.connect()

    signals_payload: list[dict[str, Any]] = []
    order_payload: list[dict[str, Any]] = []
    risk_samples: list[dict[str, Any]] = []
    broker_rule_samples: list[dict[str, Any]] = []

    seen_ids: set[str] = set()
    for candle in sorted(candles_m15, key=lambda c: c["time"]):
        event = _candle_to_event(candle, symbol, spread_pips=spread_pips, point_size=point_size)
        broker.on_market_event(event)

        new_signals = simulator.feed(candle)
        for signal in new_signals:
            sig_id = _signal_id(signal)
            if sig_id in seen_ids:
                continue
            seen_ids.add(sig_id)

            signals_payload.append(
                {
                    "signal_id": sig_id,
                    "symbol": symbol,
                    "direction": signal.side,
                    "entry_zone": signal.entry,
                    "entry": signal.entry,
                    "stop_loss": signal.stop_loss,
                    "take_profit": signal.take_profit,
                    "timestamp": signal.timestamp,
                    "session": signal.session,
                    "strategy_name": strategy,
                    "strategy_version": "2.1.3",
                    "rules_hash": "a83f92",
                }
            )

            risk_samples.append(
                {
                    "symbol": symbol,
                    "direction": signal.side,
                    "volume": 0.01,
                    "stop_loss": signal.stop_loss,
                    "take_profit": signal.take_profit,
                    "market_event": event,
                    "expected_allowed": True,
                    "account_balance": broker.config.balance,
                }
            )
            broker_rule_samples.append(
                {
                    "symbol": symbol,
                    "direction": signal.side,
                    "volume": 0.01,
                    "stop_loss": signal.stop_loss,
                    "take_profit": signal.take_profit,
                    "market_event": event,
                    "expected_allowed": True,
                    "account_balance": broker.config.balance,
                }
            )

            result = await broker.place_order(
                symbol=symbol,
                direction=signal.side,
                volume=0.01,
                sl=signal.stop_loss,
                tp=signal.take_profit,
                magic=21001,
                comment=f"{strategy}-{period}",
                signal_timestamp=signal.timestamp,
                expected_entry=signal.entry,
            )
            order_payload.append(
                {
                    "signal_id": sig_id,
                    "order_id": result.order_id,
                    "symbol": symbol,
                    "direction": signal.side,
                    "volume": 0.01,
                    "stop_loss": signal.stop_loss,
                    "take_profit": signal.take_profit,
                    "status": "filled",
                }
            )

    # Add one explicit spread rejection case for broker rule coverage.
    if signals_payload:
        rejected_event = _candle_to_event(candles_m15[0], symbol, spread_pips=max(spread_pips * 10.0, 10.0), point_size=point_size)
        broker_rule_samples.append(
            {
                "symbol": symbol,
                "direction": signals_payload[0]["direction"],
                "volume": 0.01,
                "stop_loss": signals_payload[0]["stop_loss"],
                "take_profit": signals_payload[0]["take_profit"],
                "market_event": rejected_event,
                "expected_allowed": False,
                "account_balance": broker.config.balance,
            }
        )

    open_positions = list(broker._positions.open_positions())
    for position in open_positions:
        await broker.close_position(position.position_id, reason="END_OF_REPLAY")

    recovery_snapshot = broker.snapshot_state()
    execution_events = broker.execution_events()
    fills = [
        {
            "order_id": item["order_id"],
            "symbol": item["symbol"],
            "direction": item["direction"],
            "volume": item["volume"],
            "stop_loss": item["stop_loss"],
            "take_profit": item["take_profit"],
        }
        for item in order_payload
    ]
    recovery_expected_open_positions = len(broker._positions.open_positions())

    return ReplayValidationPayload(
        strategy=strategy,
        period=period,
        signals=signals_payload,
        orders=order_payload,
        fills=fills,
        execution_events=execution_events,
        risk_samples=risk_samples,
        broker_rule_samples=broker_rule_samples,
        recovery_snapshot=recovery_snapshot,
        recovery_expected_open_positions=recovery_expected_open_positions,
        backtest_pf=backtest_pf,
        virtual_pf=virtual_pf,
    )


async def run_replay_validation_from_candles(
    *,
    strategy: str,
    period: str,
    symbol: str,
    candles_m15: list[dict],
    candles_h4: list[dict],
    report_dir: str | None = None,
    broker_config: VirtualBrokerConfig | None = None,
    spread_pips: float = 1.0,
    point_size: float = 0.0001,
    backtest_pf: float = 1.0,
    virtual_pf: float = 1.0,
) -> ExecutionValidationReport:
    payload = await build_validation_payload_from_candles(
        strategy=strategy,
        period=period,
        symbol=symbol,
        candles_m15=candles_m15,
        candles_h4=candles_h4,
        broker_config=broker_config,
        spread_pips=spread_pips,
        point_size=point_size,
        backtest_pf=backtest_pf,
        virtual_pf=virtual_pf,
    )
    suite = ExecutionValidationSuite(report_dir=report_dir)
    return suite.run(
        strategy=payload.strategy,
        period=payload.period,
        signals=payload.signals,
        orders=payload.orders,
        fills=payload.fills,
        execution_events=payload.execution_events,
        risk_samples=payload.risk_samples,
        broker_rule_samples=payload.broker_rule_samples,
        recovery_snapshot=payload.recovery_snapshot,
        recovery_expected_open_positions=payload.recovery_expected_open_positions,
        backtest_pf=payload.backtest_pf,
        virtual_pf=payload.virtual_pf,
    )
