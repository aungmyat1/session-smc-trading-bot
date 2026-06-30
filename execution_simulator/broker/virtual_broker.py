from __future__ import annotations

import itertools
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from execution.metaapi_client import AccountInfo, BrokerPosition, OrderResult, SymbolPrice
from core.broker_interface import BrokerInterface
from execution_events import ExecutionEvent
from execution_simulator.broker.order_manager import OrderManager, VirtualOrder
from execution_simulator.broker.position_manager import PositionManager, VirtualPosition
from execution_simulator.database.execution_log import ExecutionLog
from execution_simulator.execution.fill_engine import FillEngine
from execution_simulator.execution.risk_engine import RiskEngine
from execution_simulator.replay_engine.event_stream import MarketEvent


@dataclass
class VirtualBrokerConfig:
    leverage: int = 100
    balance: float = 10_000.0
    currency: str = "USD"
    contract_size_by_symbol: dict[str, float] | None = None
    point_size_by_symbol: dict[str, float] | None = None
    max_spread_pips: dict[str, float] | None = None
    min_lot: float = 0.01
    max_lot: float = 10.0
    min_stop_distance_points: int = 50
    latency_ms: int = 150
    slippage_points: float = 0.3


class VirtualBroker(BrokerInterface):
    """Virtual broker that mirrors the MetaAPI client surface used by the bot."""

    def __init__(
        self,
        feed: Any | None = None,
        *,
        config: VirtualBrokerConfig | None = None,
        execution_log: ExecutionLog | None = None,
    ) -> None:
        self.feed = feed
        self.config = config or VirtualBrokerConfig()
        self._connected = False
        self._market_event: MarketEvent | None = None
        self._events: list[ExecutionEvent] = []
        self._order_ids = itertools.count(1)
        self._position_ids = itertools.count(1)
        self._orders = OrderManager()
        self._positions = PositionManager(contract_size_by_symbol=self.config.contract_size_by_symbol)
        self._fill_engine = FillEngine(
            latency_ms=self.config.latency_ms,
            slippage_points=self.config.slippage_points,
            point_size_by_symbol=self.config.point_size_by_symbol,
        )
        self._risk_engine = RiskEngine(
            max_spread_pips=self.config.max_spread_pips,
            min_lot=self.config.min_lot,
            max_lot=self.config.max_lot,
            min_stop_distance_points=self.config.min_stop_distance_points,
            leverage=self.config.leverage,
            contract_size_by_symbol=self.config.contract_size_by_symbol,
            point_size_by_symbol=self.config.point_size_by_symbol,
        )
        self._log = execution_log or ExecutionLog()

    @property
    def is_connected(self) -> bool:
        return self._connected

    def on_market_event(self, event: MarketEvent) -> None:
        self._market_event = event
        self._check_open_positions(event)

    async def connect(self) -> None:
        self._connected = True

    async def disconnect(self) -> None:
        self._connected = False

    async def reconnect(self) -> bool:
        self._connected = True
        return True

    def connection_status(self) -> dict:
        return {
            "connected": self._connected,
            "live_trading": False,
            "account_id": "virtual",
        }

    def _require_market(self) -> MarketEvent:
        if self._market_event is None:
            raise RuntimeError("No market event available")
        return self._market_event

    def _account_info(self) -> AccountInfo:
        return AccountInfo(
            balance=self.config.balance,
            equity=self.config.balance,
            margin=0.0,
            free_margin=self.config.balance,
            leverage=self.config.leverage,
            currency=self.config.currency,
        )

    async def get_account_info(self) -> AccountInfo:
        if not self._connected:
            raise RuntimeError("Not connected")
        return self._account_info()

    async def get_account(self) -> AccountInfo:
        return await self.get_account_info()

    async def get_symbol_price(self, symbol: str) -> SymbolPrice:
        if not self._connected:
            raise RuntimeError("Not connected")
        event = self._require_market()
        point = (self.config.point_size_by_symbol or {}).get(symbol, 0.0001)
        spread_pips = round((event.ask - event.bid) / point, 2)
        return SymbolPrice(bid=event.bid, ask=event.ask, spread_pips=spread_pips, time=event.timestamp.isoformat())

    async def get_price(self, symbol: str) -> SymbolPrice:
        return await self.get_symbol_price(symbol)

    async def check_spread(self, symbol: str) -> tuple[bool, float]:
        if not self._connected:
            return False, 0.0
        try:
            price = await self.get_symbol_price(symbol)
            max_spread = (self.config.max_spread_pips or {}).get(symbol, 5.0)
            return price.spread_pips <= max_spread, price.spread_pips
        except Exception:
            return False, 0.0

    async def get_open_positions(self, magic: int | None = None) -> list[BrokerPosition]:
        if not self._connected:
            return []
        positions = self._positions.open_positions()
        if magic is not None:
            positions = [p for p in positions if p.magic == magic]
        return [
            BrokerPosition(
                position_id=p.position_id,
                symbol=p.symbol,
                direction="long" if p.direction.lower() in {"long", "buy"} else "short",
                volume=p.volume,
                open_price=p.open_price,
                sl=p.stop_loss,
                tp=p.take_profit,
                profit=p.profit,
                magic=p.magic,
            )
            for p in positions
        ]

    async def get_positions(self) -> list[BrokerPosition]:
        return await self.get_open_positions()

    def _next_order_id(self) -> str:
        return f"VIRT-ORD-{next(self._order_ids):06d}"

    def _next_position_id(self) -> str:
        return f"VIRT-POS-{next(self._position_ids):06d}"

    def _current_event(self) -> MarketEvent:
        return self._require_market()

    def _emit_event(
        self,
        event_type: str,
        *,
        order_id: str,
        price: float | None = None,
        message: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self._events.append(
            ExecutionEvent(
                event_id=f"EVT-{len(self._events) + 1:06d}",
                order_id=order_id,
                event_type=event_type,
                price=price,
                message=message,
                metadata=metadata or {},
            )
        )

    def _close_position_internal(
        self,
        position_id: str,
        close_price: float,
        close_time: datetime,
        reason: str,
    ) -> bool:
        position = self._positions.get(position_id)
        if position is None or not position.is_open:
            return False
        closed = self._positions.close_position(position_id, close_price, close_time, reason)
        self._emit_event(
            "POSITION_CLOSED",
            order_id=closed.order_id,
            price=close_price,
            message=reason,
            metadata={"symbol": closed.symbol, "position_id": closed.position_id, "profit": closed.profit},
        )
        duration = (closed.close_time - closed.open_time).total_seconds() if closed.close_time else None
        self._log.log_position(
            position_id=closed.position_id,
            order_id=closed.order_id,
            symbol=closed.symbol,
            direction=closed.direction,
            entry_price=closed.open_price,
            exit_price=closed.close_price,
            profit=closed.profit,
            duration_seconds=duration,
            exit_reason=closed.exit_reason,
            timestamp=close_time.isoformat(),
        )
        return True

    def _check_open_positions(self, market: MarketEvent) -> None:
        for position in list(self._positions.open_positions()):
            direction = position.direction.lower()
            if direction in {"long", "buy"}:
                if market.bid <= position.stop_loss:
                    self._close_position_internal(position.position_id, position.stop_loss, market.timestamp, "STOP_LOSS")
                elif market.bid >= position.take_profit:
                    self._close_position_internal(position.position_id, position.take_profit, market.timestamp, "TAKE_PROFIT")
            else:
                if market.ask >= position.stop_loss:
                    self._close_position_internal(position.position_id, position.stop_loss, market.timestamp, "STOP_LOSS")
                elif market.ask <= position.take_profit:
                    self._close_position_internal(position.position_id, position.take_profit, market.timestamp, "TAKE_PROFIT")

    async def place_order(
        self,
        symbol: str,
        direction: str,
        volume: float,
        sl: float,
        tp: float,
        magic: int,
        comment: str = "",
        signal_timestamp: datetime | None = None,
        expected_entry: float | None = None,
    ) -> OrderResult:
        if not self._connected:
            raise RuntimeError("Not connected")

        market = self._current_event()
        open_positions = self._positions.open_positions()
        same_symbol_positions = self._positions.open_positions(symbol=symbol)
        risk = self._risk_engine.validate_order(
            symbol=symbol,
            direction=direction,
            volume=volume,
            stop_loss=sl,
            take_profit=tp,
            market_event=market,
            open_positions=len(open_positions),
            same_symbol_positions=len(same_symbol_positions),
            account_balance=self.config.balance,
        )
        order_id = self._next_order_id()
        self._emit_event(
            "ORDER_RECEIVED",
            order_id=order_id,
            message=f"{direction.upper()} {symbol} volume={volume}",
            metadata={"symbol": symbol, "direction": direction, "volume": volume},
        )
        self._orders.submit(
            VirtualOrder(
                order_id=order_id,
                symbol=symbol,
                direction=direction,
                volume=volume,
                stop_loss=sl,
                take_profit=tp,
                requested_at=signal_timestamp or market.timestamp,
                magic=magic,
                comment=comment,
            )
        )

        if not risk.allowed:
            self._emit_event(
                "ORDER_VALIDATED",
                order_id=order_id,
                message=risk.reason,
                metadata={"symbol": symbol, "allowed": False, "spread_pips": risk.spread_pips},
            )
            self._emit_event(
                "ORDER_REJECTED",
                order_id=order_id,
                message=risk.reason,
                metadata={"symbol": symbol, "spread_pips": risk.spread_pips},
            )
            self._orders.mark_rejected(order_id, risk.reason)
            self._log.log_order(
                order_id=order_id,
                symbol=symbol,
                direction=direction,
                requested_price=None,
                filled_price=None,
                slippage=0.0,
                latency_ms=0,
                status="rejected",
                reason=risk.reason,
                timestamp=market.timestamp.isoformat(),
            )
            raise RuntimeError(risk.reason)

        self._emit_event(
            "ORDER_VALIDATED",
            order_id=order_id,
            price=market.ask if direction.lower() in {"long", "buy"} else market.bid,
            message="accepted",
            metadata={
                "symbol": symbol,
                "allowed": True,
                "spread_pips": risk.spread_pips,
                "required_margin": risk.required_margin,
            },
        )
        fill = self._fill_engine.fill_order(order_id, symbol, direction, market)
        self._emit_event(
            "ORDER_FILLED",
            order_id=order_id,
            price=fill.filled_price,
            message=f"latency={fill.latency_ms}ms slippage={fill.slippage:.5f}",
            metadata={
                "symbol": symbol,
                "requested_price": fill.requested_price,
                "filled_price": fill.filled_price,
                "slippage": fill.slippage,
                "latency_ms": fill.latency_ms,
                "point_size": (self.config.point_size_by_symbol or {}).get(symbol, 0.0001),
            },
        )
        self._orders.update_fill(
            order_id,
            filled_at=fill.filled_at,
            filled_price=fill.filled_price,
            requested_price=fill.requested_price,
            slippage=fill.slippage,
            latency_ms=fill.latency_ms,
        )

        position_id = self._next_position_id()
        position = VirtualPosition(
            position_id=position_id,
            order_id=order_id,
            symbol=symbol,
            direction=direction,
            volume=volume,
            open_price=fill.filled_price,
            stop_loss=sl,
            take_profit=tp,
            open_time=fill.filled_at,
            magic=magic,
            comment=comment,
            metadata={
                "requested_price": fill.requested_price,
                "signal_timestamp": signal_timestamp.isoformat() if signal_timestamp else None,
                "expected_entry": expected_entry,
                "filled_price": fill.filled_price,
                "slippage": fill.slippage,
                "latency_ms": fill.latency_ms,
            },
        )
        self._positions.open_position(position)
        self._emit_event(
            "POSITION_OPENED",
            order_id=order_id,
            price=fill.filled_price,
            message=position.position_id,
            metadata={"symbol": symbol, "position_id": position.position_id},
        )

        self._log.log_order(
            order_id=order_id,
            symbol=symbol,
            direction=direction,
            requested_price=fill.requested_price,
            filled_price=fill.filled_price,
            slippage=fill.slippage,
            latency_ms=fill.latency_ms,
            status="filled",
            timestamp=fill.filled_at.isoformat(),
        )
        self._log.log_position(
            position_id=position_id,
            order_id=order_id,
            symbol=symbol,
            direction=direction,
            entry_price=fill.filled_price,
            exit_price=None,
            profit=None,
            duration_seconds=None,
            exit_reason="",
            timestamp=fill.filled_at.isoformat(),
        )
        self._log.log_fill(
            order_id=order_id,
            symbol=symbol,
            direction=direction,
            execution_time=fill.filled_at.isoformat(),
            slippage=fill.slippage,
            latency_ms=fill.latency_ms,
            requested_price=fill.requested_price,
            filled_price=fill.filled_price,
        )
        if signal_timestamp is not None or expected_entry is not None:
            self._log.log_signal_comparison(
                symbol=symbol,
                expected_direction=direction,
                actual_direction=direction,
                expected_entry=expected_entry,
                actual_entry=fill.filled_price,
                slippage=fill.slippage,
                latency_ms=fill.latency_ms,
                verdict="PASS",
                timestamp=fill.filled_at.isoformat(),
            )

        return OrderResult(
            order_id=order_id,
            symbol=symbol,
            direction=direction,
            volume=volume,
            entry_price=fill.filled_price,
            sl=sl,
            tp=tp,
            dry_run=True,
        )

    async def send_order(self, order: dict | Any) -> OrderResult:
        if isinstance(order, dict):
            return await self.place_order(
                symbol=order["symbol"],
                direction=order.get("direction", order.get("type", "")),
                volume=float(order["volume"]),
                sl=float(order["SL"] if "SL" in order else order.get("sl") or 0.0),
                tp=float(order["TP"] if "TP" in order else order.get("tp") or 0.0),
                magic=int(order.get("magic", 0)),
                comment=str(order.get("comment", "")),
                signal_timestamp=order.get("signal_timestamp"),
                expected_entry=order.get("expected_entry"),
            )
        return await self.place_order(
            symbol=getattr(order, "symbol"),
            direction=getattr(order, "direction", getattr(order, "type", "")),
            volume=float(getattr(order, "volume")),
            sl=float(getattr(order, "stop_loss", getattr(order, "sl"))),
            tp=float(getattr(order, "take_profit", getattr(order, "tp"))),
            magic=int(getattr(order, "magic", 0)),
            comment=str(getattr(order, "comment", "")),
            signal_timestamp=getattr(order, "signal_timestamp", None),
            expected_entry=getattr(order, "expected_entry", None),
        )

    async def modify_order(self, order_id: str, sl: float | None = None, tp: float | None = None, **changes: Any) -> bool:
        order = self._orders.get(order_id)
        if order is None or not self._connected:
            return False
        if sl is None:
            sl = changes.get("stop_loss")
        if tp is None:
            tp = changes.get("take_profit")
        if sl is not None:
            order.stop_loss = float(sl)
        if tp is not None:
            order.take_profit = float(tp)
        return True

    async def close_position(self, position_id: str, reason: str = "MANUAL") -> bool:
        if not self._connected:
            return False
        market = self._current_event()
        position = self._positions.get(position_id)
        if position is None or not position.is_open:
            return False
        close_price = market.bid if position.direction.lower() in {"long", "buy"} else market.ask
        return self._close_position_internal(position_id, close_price, market.timestamp, reason)

    def execution_events(self) -> list[ExecutionEvent]:
        return list(self._events)

    async def close_order(self, order_id: str) -> bool:
        if not self._connected:
            return False
        for position in self._positions.open_positions():
            if position.order_id == order_id or position.position_id == order_id:
                return await self.close_position(position.position_id, reason="ORDER_CLOSED")
        return False

    def execution_summary(self) -> dict[str, int]:
        return self._log.summary()

    def snapshot_state(self) -> dict[str, Any]:
        return {
            "connected": self._connected,
            "market_event": {
                "timestamp": self._market_event.timestamp.isoformat() if self._market_event else None,
                "symbol": self._market_event.symbol if self._market_event else None,
                "bid": self._market_event.bid if self._market_event else None,
                "ask": self._market_event.ask if self._market_event else None,
                "volume": self._market_event.volume if self._market_event else None,
            },
            "orders": [
                {
                    "order_id": order.order_id,
                    "symbol": order.symbol,
                    "direction": order.direction,
                    "volume": order.volume,
                    "stop_loss": order.stop_loss,
                    "take_profit": order.take_profit,
                    "requested_at": order.requested_at.isoformat(),
                    "status": order.status,
                    "filled_at": order.filled_at.isoformat() if order.filled_at else None,
                    "filled_price": order.filled_price,
                    "requested_price": order.requested_price,
                    "slippage": order.slippage,
                    "latency_ms": order.latency_ms,
                    "magic": order.magic,
                    "comment": order.comment,
                    "metadata": order.metadata,
                }
                for order in self._orders.all()
            ],
            "positions": [
                {
                    "position_id": position.position_id,
                    "order_id": position.order_id,
                    "symbol": position.symbol,
                    "direction": position.direction,
                    "volume": position.volume,
                    "open_price": position.open_price,
                    "stop_loss": position.stop_loss,
                    "take_profit": position.take_profit,
                    "open_time": position.open_time.isoformat(),
                    "magic": position.magic,
                    "comment": position.comment,
                    "close_time": position.close_time.isoformat() if position.close_time else None,
                    "close_price": position.close_price,
                    "exit_reason": position.exit_reason,
                    "profit": position.profit,
                    "metadata": position.metadata,
                }
                for position in self._positions.open_positions() + self._positions.closed_positions()
            ],
            "events": [
                {
                    "event_id": event.event_id,
                    "timestamp": event.timestamp.isoformat(),
                    "order_id": event.order_id,
                    "event_type": event.event_type,
                    "price": event.price,
                    "message": event.message,
                    "metadata": event.metadata,
                }
                for event in self._events
            ],
        }

    @classmethod
    def restore_state(
        cls,
        snapshot: dict[str, Any],
        *,
        feed: Any | None = None,
        config: VirtualBrokerConfig | None = None,
        execution_log: ExecutionLog | None = None,
    ) -> "VirtualBroker":
        broker = cls(feed=feed, config=config, execution_log=execution_log)
        broker._connected = bool(snapshot.get("connected", False))

        market = snapshot.get("market_event") or {}
        ts = market.get("timestamp")
        if ts and market.get("symbol") is not None:
            broker._market_event = MarketEvent(
                timestamp=datetime.fromisoformat(ts),
                symbol=str(market["symbol"]),
                bid=float(market["bid"]),
                ask=float(market["ask"]),
                volume=float(market.get("volume", 0.0)),
            )

        for item in snapshot.get("positions", []):
            position = VirtualPosition(
                position_id=str(item["position_id"]),
                order_id=str(item["order_id"]),
                symbol=str(item["symbol"]),
                direction=str(item["direction"]),
                volume=float(item["volume"]),
                open_price=float(item["open_price"]),
                stop_loss=float(item["stop_loss"]),
                take_profit=float(item["take_profit"]),
                open_time=datetime.fromisoformat(item["open_time"]),
                magic=int(item.get("magic", 0)),
                comment=str(item.get("comment", "")),
                close_time=datetime.fromisoformat(item["close_time"]) if item.get("close_time") else None,
                close_price=item.get("close_price"),
                exit_reason=str(item.get("exit_reason", "")),
                profit=float(item.get("profit", 0.0)),
                metadata=dict(item.get("metadata", {})),
            )
            broker._positions.open_position(position)
        return broker
