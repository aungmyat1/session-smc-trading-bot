"""
Trade Manager — open/close/modify/emergency for strategy demo execution.

Isolated from existing execution/order_manager.py.
All write operations require DEMO_ONLY=false AND explicit call.

Public API:
    TradeManager(executor)
        async .open_position(signal, lots) -> dict
        async .close_position(position_id) -> bool
        async .modify_sl_tp(position_id, sl, tp) -> bool
        async .get_positions() -> list[dict]
        async .emergency_close_all() -> int  (count closed)
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from execution.execution_state import ExecutionStateStore, RetryPolicy
from execution.vantage_demo_executor import VantageDemoExecutor
from monitoring.telegram import TelegramAlerter

_log = logging.getLogger("strategy_demo.trade_manager")

_MAGIC = 21099   # shared demo magic number
_ORDER_RETRY_ATTEMPTS = 3
_ORDER_RETRY_BASE_DELAY_S = 1.0


class TradeManager:
    def __init__(
        self,
        executor: VantageDemoExecutor,
        telegram: TelegramAlerter | None = None,
        execution_store: ExecutionStateStore | None = None,
    ) -> None:
        self._ex = executor
        self._telegram = telegram
        self._store = execution_store or ExecutionStateStore(".")
        self._retry_policy = RetryPolicy(
            operation="broker_place_order",
            max_attempts=_ORDER_RETRY_ATTEMPTS,
            backoff_strategy="exponential",
            retryable_errors=["timeout", "temporarily unavailable", "connection reset"],
            ambiguity_policy="reconcile_before_retry",
        )

    async def open_position(self, signal, lots: float, execution_context: dict | None = None) -> dict:
        """
        Open a position from a strategy Signal dataclass or signal-like object.

        signal must have: symbol/pair, side/direction, entry, stop_loss/sl, take_profit/tp
        Returns order result dict.
        """
        symbol    = getattr(signal, "pair", None) or signal.get("symbol", "")
        direction = getattr(signal, "side", None) or signal.get("direction", "")
        sl        = getattr(signal, "stop_loss", None) or signal.get("stop_loss", 0.0)
        tp        = getattr(signal, "take_profit", None) or signal.get("take_profit", 0.0)

        # Normalise direction
        direction = direction.lower()
        if direction in ("long",):
            direction = "buy"
        elif direction in ("short",):
            direction = "sell"

        _log.info("Opening %s %s %.4f lots SL=%.5f TP=%.5f", direction, symbol, lots, sl, tp)
        strategy_name = getattr(signal, "strategy_name", "") or "strategy-demo"
        signal_ts = getattr(signal, "timestamp", None)
        signal_id = f"{strategy_name}:{symbol}:{direction}:{getattr(signal_ts, 'isoformat', lambda: '')()}"
        record = self._store.create_record(
            strategy_id=strategy_name,
            strategy_version=str(execution_context.get("strategy_version", "")) if execution_context else "",
            signal_id=signal_id,
            metadata={
                "symbol": symbol,
                "direction": direction,
                "lots": lots,
            },
        )
        if execution_context and execution_context.get("governance"):
            self._store.transition(
                record.execution_id,
                "GOVERNANCE_VALIDATED",
                metadata=execution_context["governance"],
            )
        if execution_context and execution_context.get("permission"):
            self._store.transition(
                record.execution_id,
                "PERMISSION_VALIDATED",
                metadata=execution_context["permission"],
            )
        self._store.transition(record.execution_id, "RISK_APPROVED", metadata={"lots": lots})
        self._store.transition(record.execution_id, "SUBMISSION_PENDING", metadata=self._retry_policy.to_dict())

        result = await self._place_order_with_retry(
            execution_id=record.execution_id,
            symbol=symbol,
            direction=direction,
            lots=lots,
            sl=sl,
            tp=tp,
            magic=_MAGIC,
            comment=strategy_name[:31],
        )
        result["opened_at"] = datetime.now(timezone.utc).isoformat()
        result["execution_id"] = record.execution_id
        result["idempotency_key"] = record.idempotency_key
        return result

    async def close_position(self, position_id: str) -> bool:
        _log.info("Closing position %s", position_id)
        return await self._ex.close_position(position_id)

    async def modify_sl_tp(self, position_id: str, sl: float, tp: float) -> bool:
        _log.info("Modifying %s SL=%.5f TP=%.5f", position_id, sl, tp)
        return await self._ex.modify_position(position_id, sl, tp)

    async def get_positions(self) -> list[dict]:
        positions = await self._ex.get_positions()
        return [p for p in positions if p.get("magic") == _MAGIC]

    async def emergency_close_all(self) -> int:
        """Force-close all ST-A2 positions. Returns count closed."""
        positions = await self.get_positions()
        count = 0
        for p in positions:
            pid = p.get("id", "")
            if pid:
                ok = await self.close_position(pid)
                if ok:
                    count += 1
                    _log.warning("EMERGENCY CLOSE: %s %s", p.get("symbol"), pid)
        _log.warning("Emergency close: %d positions closed.", count)
        return count

    def mark_execution_state(self, execution_id: str, state: str, metadata: dict | None = None) -> None:
        self._store.transition(execution_id, state, metadata=metadata or {})

    async def _place_order_with_retry(self, *, execution_id: str, **kwargs) -> dict:
        last_exc: Exception | None = None
        for attempt in range(1, _ORDER_RETRY_ATTEMPTS + 1):
            try:
                result = await self._ex.place_order(**kwargs)
                order_id = str(result.get("order_id", ""))
                self._store.transition(
                    execution_id,
                    "BROKER_ACKNOWLEDGED",
                    metadata={"attempt": attempt},
                    broker_order_id=order_id,
                    position_ref=order_id,
                )
                return result
            except Exception as exc:
                last_exc = exc
                classification = self._classify_error(exc)
                if classification == "ambiguous":
                    self._store.transition(
                        execution_id,
                        "RECOVERY_PENDING",
                        metadata={"attempt": attempt, "error": str(exc)},
                    )
                    break
                if classification == "terminal" or attempt >= _ORDER_RETRY_ATTEMPTS:
                    break
                delay = _ORDER_RETRY_BASE_DELAY_S * (2 ** (attempt - 1))
                self._store.transition(
                    execution_id,
                    "SUBMISSION_PENDING",
                    metadata={"attempt": attempt, "delay_seconds": delay, "error": str(exc)},
                )
                _log.warning(
                    "place_order attempt %d/%d failed: %s — retrying in %.1fs",
                    attempt,
                    _ORDER_RETRY_ATTEMPTS,
                    exc,
                    delay,
                )
                await asyncio.sleep(delay)
        assert last_exc is not None
        self._store.transition(
            execution_id,
            "FAILED_TERMINAL" if self._classify_error(last_exc) != "ambiguous" else "RECOVERY_PENDING",
            metadata={"error": str(last_exc)},
        )
        if self._telegram is not None:
            await self._telegram.send_error(
                f"Order placement exhausted after {_ORDER_RETRY_ATTEMPTS} attempts: {last_exc}"
            )
        raise last_exc

    def _classify_error(self, exc: Exception) -> str:
        message = str(exc).strip().lower()
        if any(token in message for token in ("timeout", "timed out", "no response", "unknown execution state")):
            return "ambiguous"
        if any(token in message for token in self._retry_policy.retryable_errors):
            return "transient"
        return "terminal"
