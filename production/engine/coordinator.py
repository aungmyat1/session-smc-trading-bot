"""Canonical market-to-journal coordinator for System 2."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Callable

from production.engine.contracts import ExecutionSignal, MarketDataPort, SignalAction, StrategyRuntime
from production.engine.execution_pipeline import AdapterResult, CanonicalExecutionPipeline, ExecutionIntent


class ExecutionCoordinator:
    def __init__(
        self,
        *,
        market_data: MarketDataPort,
        strategy: StrategyRuntime,
        pipeline: CanonicalExecutionPipeline,
        quantity_resolver: Callable[[ExecutionSignal], float],
        max_signal_age_seconds: int = 300,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.market_data = market_data
        self.strategy = strategy
        self.pipeline = pipeline
        self.quantity_resolver = quantity_resolver
        self.max_signal_age_seconds = max_signal_age_seconds
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self._seen: dict[str, datetime] = {}

    async def run(self) -> None:
        await self.market_data.connect()
        try:
            health = await self.market_data.health()
            if str(health.get("status", "")).upper() not in {"PASS", "HEALTHY"}:
                raise RuntimeError("market data health gate failed")
            async for event in self.market_data.stream():
                signal = self.strategy.on_market_event(event)
                if signal.action is SignalAction.NONE:
                    continue
                await self.submit_signal(signal)
        finally:
            await self.market_data.disconnect()

    async def submit_signal(self, signal: ExecutionSignal) -> AdapterResult:
        now_value = self.clock()
        if now_value.tzinfo is None or signal.timestamp.tzinfo is None:
            return AdapterResult("REJECTED", details={"reason": "TIMEZONE_REQUIRED"})
        now = now_value.astimezone(timezone.utc)
        cutoff = now.timestamp() - self.max_signal_age_seconds
        self._seen = {key: stamp for key, stamp in self._seen.items() if stamp.timestamp() >= cutoff}
        if signal.signal_id in self._seen:
            return AdapterResult("REJECTED", details={"reason": "DUPLICATE_SIGNAL"})
        age = (now - signal.timestamp.astimezone(timezone.utc)).total_seconds()
        if age < 0 or age > self.max_signal_age_seconds:
            return AdapterResult("REJECTED", details={"reason": "STALE_SIGNAL"})
        self._seen[signal.signal_id] = now
        side = "buy" if signal.action is SignalAction.BUY else "sell" if signal.action is SignalAction.SELL else "close"
        intent_id = hashlib.sha256(f"{signal.signal_id}:{signal.symbol}:{signal.action}".encode()).hexdigest()
        intent = ExecutionIntent(
            intent_id=intent_id,
            strategy_id=self.pipeline.context.strategy_id if self.pipeline.context else "",
            symbol=signal.symbol,
            side=side,
            quantity=self.quantity_resolver(signal),
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            metadata={**dict(signal.metadata), "signal_id": signal.signal_id, "risk_percent": signal.risk_percent or 0.0},
        )
        return await self.pipeline.submit(intent)
