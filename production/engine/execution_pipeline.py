"""Canonical, adapter-driven System 2 execution pipeline.

The pipeline owns execution ordering and event normalization.  Strategy logic,
risk policy calculations, and broker-specific behavior remain behind ports.
There is deliberately no live adapter in this build.
"""

from __future__ import annotations

from collections.abc import AsyncIterable, Awaitable, Callable, Mapping
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any, Protocol
from uuid import uuid4

from production.engine.runtime import RuntimeContext
from shared.serialization import now_iso


class ExecutionMode(StrEnum):
    REPLAY = "replay"
    VIRTUAL_DEMO = "virtual_demo"
    DEMO = "demo"


@dataclass(frozen=True, slots=True)
class ExecutionIntent:
    intent_id: str
    strategy_id: str
    symbol: str
    side: str
    quantity: float
    stop_loss: float | None = None
    take_profit: float | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RiskDecision:
    approved: bool
    reason: str
    details: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AdapterResult:
    status: str
    reference: str = ""
    details: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class NormalizedExecutionEvent:
    schema: str
    event_id: str
    timestamp: str
    event_type: str
    owner_id: str
    package_id: str
    mode: str
    intent_id: str
    strategy_id: str
    symbol: str
    side: str
    quantity: float
    approved: bool | None
    reason: str
    status: str
    reference: str
    details: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class RiskGate(Protocol):
    def evaluate(self, intent: ExecutionIntent) -> RiskDecision | Awaitable[RiskDecision]: ...


class ExecutionAdapter(Protocol):
    mode: ExecutionMode

    async def execute(self, intent: ExecutionIntent) -> AdapterResult: ...


EventSink = Callable[[NormalizedExecutionEvent], None]
PipelineWorkload = Callable[["CanonicalExecutionPipeline"], Awaitable[None]]


class CanonicalExecutionPipeline:
    """The sole authoritative ordering for execution in every available mode."""

    EVENT_SCHEMA = "execution-event/v1"

    def __init__(
        self,
        *,
        mode: str | ExecutionMode,
        risk_gate: RiskGate,
        adapter: ExecutionAdapter,
        event_sink: EventSink | None = None,
        clock: Callable[[], str] | None = None,
    ) -> None:
        try:
            self.mode = ExecutionMode(mode)
        except ValueError as exc:
            raise ValueError(f"unsupported execution mode: {mode}") from exc
        if adapter.mode is not self.mode:
            raise ValueError(f"adapter mode {adapter.mode} does not match pipeline mode {self.mode}")
        self.risk_gate = risk_gate
        self.adapter = adapter
        self.event_sink = event_sink
        self.clock = clock or now_iso
        self._context: RuntimeContext | None = None
        self.events: list[NormalizedExecutionEvent] = []

    async def run(self, context: RuntimeContext, workload: PipelineWorkload) -> None:
        if self._context is not None:
            raise RuntimeError("canonical execution pipeline is already started")
        self._context = context
        self._emit("pipeline_started", status="READY")
        try:
            await workload(self)
        finally:
            self._emit("pipeline_stopped", status="STOPPED")

    async def submit(self, intent: ExecutionIntent) -> AdapterResult:
        if self._context is None:
            raise RuntimeError("canonical execution pipeline has not started")
        self._emit("intent_received", intent=intent, status="RECEIVED")
        decision_value = self.risk_gate.evaluate(intent)
        decision = await decision_value if isinstance(decision_value, Awaitable) else decision_value
        self._emit(
            "risk_decision",
            intent=intent,
            approved=decision.approved,
            reason=decision.reason,
            status="APPROVED" if decision.approved else "REJECTED",
            details=decision.details,
        )
        if not decision.approved:
            return AdapterResult("REJECTED", details={"reason": decision.reason})
        result = await self.adapter.execute(intent)
        self._emit(
            "execution_result",
            intent=intent,
            approved=True,
            status=result.status,
            reference=result.reference,
            details=result.details,
        )
        return result

    def _emit(
        self,
        event_type: str,
        *,
        intent: ExecutionIntent | None = None,
        approved: bool | None = None,
        reason: str = "",
        status: str = "",
        reference: str = "",
        details: Mapping[str, Any] | None = None,
    ) -> None:
        context = self._context
        event = NormalizedExecutionEvent(
            schema=self.EVENT_SCHEMA,
            event_id=str(uuid4()),
            timestamp=self.clock(),
            event_type=event_type,
            owner_id=context.owner_id if context else "",
            package_id=context.package_id if context else "",
            mode=self.mode,
            intent_id=intent.intent_id if intent else "",
            strategy_id=intent.strategy_id if intent else (context.strategy_id if context else ""),
            symbol=intent.symbol if intent else "",
            side=intent.side if intent else "",
            quantity=intent.quantity if intent else 0.0,
            approved=approved,
            reason=reason,
            status=status,
            reference=reference,
            details=details or {},
        )
        self.events.append(event)
        if self.event_sink is not None:
            self.event_sink(event)


class ReplayExecutionAdapter:
    """Non-writing replay adapter; it has no broker dependency by design."""

    mode = ExecutionMode.REPLAY

    async def execute(self, intent: ExecutionIntent) -> AdapterResult:
        return AdapterResult("SIMULATED", reference=f"replay:{intent.intent_id}")


class CallbackExecutionAdapter:
    """Adapter for existing virtual-demo and demo implementations."""

    def __init__(
        self,
        mode: str | ExecutionMode,
        callback: Callable[[ExecutionIntent], Awaitable[AdapterResult]],
    ) -> None:
        self.mode = ExecutionMode(mode)
        if self.mode is ExecutionMode.REPLAY:
            raise ValueError("replay must use the non-writing ReplayExecutionAdapter")
        self._callback = callback

    async def execute(self, intent: ExecutionIntent) -> AdapterResult:
        return await self._callback(intent)


class VirtualDemoExecutionAdapter(CallbackExecutionAdapter):
    def __init__(self, callback: Callable[[ExecutionIntent], Awaitable[AdapterResult]]) -> None:
        super().__init__(ExecutionMode.VIRTUAL_DEMO, callback)


class DemoExecutionAdapter(CallbackExecutionAdapter):
    def __init__(self, callback: Callable[[ExecutionIntent], Awaitable[AdapterResult]]) -> None:
        super().__init__(ExecutionMode.DEMO, callback)


class AllowAllRiskGate:
    """Explicit gate for modes whose existing policy has already approved intent."""

    def evaluate(self, intent: ExecutionIntent) -> RiskDecision:
        return RiskDecision(True, "risk policy approved")


async def submit_all(
    pipeline: CanonicalExecutionPipeline,
    intents: AsyncIterable[ExecutionIntent],
) -> None:
    async for intent in intents:
        await pipeline.submit(intent)
