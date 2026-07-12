from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from production.engine.execution_pipeline import (
    AdapterResult,
    AllowAllRiskGate,
    CallbackExecutionAdapter,
    CanonicalExecutionPipeline,
    DemoExecutionAdapter,
    EmergencyStopRiskGate,
    ExecutionIntent,
    ExecutionMode,
    ReplayExecutionAdapter,
    RiskDecision,
    VirtualDemoExecutionAdapter,
)
from production.engine.runtime import RuntimeAuthority, RuntimeContext
from shared.strategy_package import build_canonical_package

PRIVATE_KEY = "11" * 32
PUBLIC_KEY = "d04ab232742bb4ab3a1368bd4615e4e6d0224ab71a016baf8520a332c9778737"


class _RiskGate:
    def __init__(self, approved: bool = True) -> None:
        self.approved = approved
        self.calls = 0

    def evaluate(self, _intent: ExecutionIntent) -> RiskDecision:
        self.calls += 1
        return RiskDecision(self.approved, "approved" if self.approved else "daily loss limit")


def _context() -> RuntimeContext:
    return RuntimeContext("owner", "/package", "package", "sha", "ST-A2", "2.1", ("EURUSD",), "vantage-demo", "demo-risk-firewall")


def _intent() -> ExecutionIntent:
    return ExecutionIntent("intent-1", "ST-A2", "EURUSD", "buy", 0.1, 1.09, 1.12)


@pytest.mark.asyncio
async def test_replay_adapter_emits_normalized_events_without_broker() -> None:
    gate = _RiskGate()
    pipeline = CanonicalExecutionPipeline(mode="replay", risk_gate=gate, adapter=ReplayExecutionAdapter())

    async def workload(active: CanonicalExecutionPipeline) -> None:
        result = await active.submit(_intent())
        assert result.status == "SIMULATED"

    await pipeline.run(_context(), workload)
    result_event = next(event for event in pipeline.events if event.event_type == "execution_result")
    assert result_event.schema == "execution-event/v1"
    assert result_event.mode == "replay"
    assert result_event.package_id == "package"
    assert result_event.intent_id == "intent-1"
    assert not hasattr(pipeline.adapter, "broker")


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", [ExecutionMode.VIRTUAL_DEMO, ExecutionMode.DEMO])
async def test_writing_adapters_use_same_pipeline_and_event_contract(mode: ExecutionMode) -> None:
    execute = AsyncMock(return_value=AdapterResult("FILLED", "order-1"))
    adapter = VirtualDemoExecutionAdapter(execute) if mode is ExecutionMode.VIRTUAL_DEMO else DemoExecutionAdapter(execute)
    pipeline = CanonicalExecutionPipeline(
        mode=mode,
        risk_gate=_RiskGate(),
        adapter=adapter,
    )

    async def workload(active: CanonicalExecutionPipeline) -> None:
        await active.submit(_intent())

    await pipeline.run(_context(), workload)
    execute.assert_awaited_once_with(_intent())
    result_event = next(event for event in pipeline.events if event.event_type == "execution_result")
    assert result_event.schema == "execution-event/v1"
    assert result_event.mode == mode
    assert result_event.status == "FILLED"


@pytest.mark.asyncio
async def test_risk_rejection_prevents_demo_adapter_call() -> None:
    execute = AsyncMock(return_value=AdapterResult("FILLED"))
    pipeline = CanonicalExecutionPipeline(
        mode="demo",
        risk_gate=_RiskGate(False),
        adapter=DemoExecutionAdapter(execute),
    )

    async def workload(active: CanonicalExecutionPipeline) -> None:
        result = await active.submit(_intent())
        assert result.status == "REJECTED"

    await pipeline.run(_context(), workload)
    execute.assert_not_awaited()
    assert any(event.reason == "daily loss limit" for event in pipeline.events)


@pytest.mark.asyncio
async def test_all_modes_emit_identical_normalized_event_fields() -> None:
    observed: list[set[str]] = []
    for mode in ExecutionMode:
        adapter = ReplayExecutionAdapter() if mode is ExecutionMode.REPLAY else CallbackExecutionAdapter(
            mode, AsyncMock(return_value=AdapterResult("SIMULATED"))
        )
        pipeline = CanonicalExecutionPipeline(mode=mode, risk_gate=_RiskGate(), adapter=adapter)

        async def workload(active: CanonicalExecutionPipeline) -> None:
            await active.submit(_intent())

        await pipeline.run(_context(), workload)
        observed.append(set(next(event for event in pipeline.events if event.event_type == "execution_result").to_dict()))
    assert observed[0] == observed[1] == observed[2]


@pytest.mark.parametrize("mode", ["live", "shadow", "invalid"])
def test_invalid_or_unavailable_modes_are_rejected(mode: str) -> None:
    with pytest.raises(ValueError, match="unsupported execution mode"):
        CanonicalExecutionPipeline(mode=mode, risk_gate=_RiskGate(), adapter=ReplayExecutionAdapter())


@pytest.mark.asyncio
async def test_runtime_validates_package_before_pipeline_construction(tmp_path: Path) -> None:
    build = build_canonical_package(
        tmp_path / "package.tar.gz",
        strategy_id="ST-A2",
        strategy_version="2.1",
        adapter_id="ST2Adapter",
        adapter_version="2.1",
        strategy_spec="# test\n",
        parameters={"symbols": ["EURUSD"]},
        risk_policy={"policy_id": "demo", "live_trading_enabled": False},
        evidence={"replay": {"status": "PASS"}},
        governance_snapshot={"strategies": {"ST-A2": {"latest_version": "2.1", "evidence_count": 1, "decision_count": 1, "approval_count": 1, "latest_approval": None}}},
        approval={"decision": "APPROVED", "approved_at": "2026-01-01T00:00:00+00:00", "expires_at": "2099-01-01T00:00:00+00:00", "revoked": False},
        signing_key=PRIVATE_KEY,
    )
    authority = RuntimeAuthority(root=tmp_path, package_path=build.archive_path, verifying_public_key="22" * 32)
    constructed = False

    def factory(_context: RuntimeContext) -> CanonicalExecutionPipeline:
        nonlocal constructed
        constructed = True
        return CanonicalExecutionPipeline(mode="replay", risk_gate=_RiskGate(), adapter=ReplayExecutionAdapter())

    async def workload(_pipeline: CanonicalExecutionPipeline) -> None:
        raise AssertionError("must not run")

    with pytest.raises(PermissionError):
        await authority.run_pipeline(factory, workload)
    assert constructed is False


class _CountingAdapter(CallbackExecutionAdapter):
    def __init__(self) -> None:
        self.calls = 0

        async def _execute(_intent: ExecutionIntent) -> AdapterResult:
            self.calls += 1
            return AdapterResult("SUBMITTED", reference="order-1")

        super().__init__(ExecutionMode.DEMO, _execute)


def test_emergency_stop_gate_rejects_when_active() -> None:
    gate = EmergencyStopRiskGate(
        AllowAllRiskGate(),
        state_loader=lambda: {"emergency_stop": {"active": True, "reason": "manual pause", "activated_at": "t1", "source": "control_pause"}},
    )

    decision = gate.evaluate(_intent())

    assert decision.approved is False
    assert decision.reason == "emergency stop active"
    assert decision.details["reason"] == "manual pause"
    assert decision.details["source"] == "control_pause"


def test_emergency_stop_gate_delegates_to_inner_when_inactive() -> None:
    inner = _RiskGate(approved=True)
    gate = EmergencyStopRiskGate(inner, state_loader=lambda: {"emergency_stop": {"active": False}})

    decision = gate.evaluate(_intent())

    assert decision.approved is True
    assert inner.calls == 1


def test_emergency_stop_gate_rejects_even_when_inner_would_approve() -> None:
    inner = _RiskGate(approved=True)
    gate = EmergencyStopRiskGate(inner, state_loader=lambda: {"emergency_stop": {"active": True, "reason": "close-all"}})

    decision = gate.evaluate(_intent())

    assert decision.approved is False
    assert inner.calls == 0  # inner gate never consulted once emergency stop is active


def test_emergency_stop_gate_reads_state_fresh_on_every_call_not_cached() -> None:
    """Regression: a stop activated or cleared mid-run must take effect on
    the very next intent, not just at gate construction time."""
    active = {"emergency_stop": {"active": True, "reason": "manual pause"}}
    gate = EmergencyStopRiskGate(AllowAllRiskGate(), state_loader=lambda: active)

    first = gate.evaluate(_intent())
    active["emergency_stop"] = {"active": False}
    second = gate.evaluate(_intent())

    assert first.approved is False
    assert second.approved is True


def test_emergency_stop_gate_does_not_forward_context_to_a_single_arg_inner_gate() -> None:
    """Regression: AllowAllRiskGate (and any other RiskGate declaring only
    evaluate(self, intent)) must not receive a context arg it can't accept —
    previously this raised TypeError whenever a context was supplied."""
    gate = EmergencyStopRiskGate(AllowAllRiskGate(), state_loader=lambda: {"emergency_stop": {"active": False}})

    decision = gate.evaluate(_intent(), context={"some": "context"})

    assert decision.approved is True


def test_emergency_stop_gate_forwards_context_to_a_context_aware_inner_gate() -> None:
    class _ContextAwareGate:
        def __init__(self) -> None:
            self.received_context = None

        def evaluate(self, _intent: ExecutionIntent, context: object = None) -> RiskDecision:
            self.received_context = context
            return RiskDecision(True, "approved with context")

    inner = _ContextAwareGate()
    gate = EmergencyStopRiskGate(inner, state_loader=lambda: {"emergency_stop": {"active": False}})

    gate.evaluate(_intent(), context={"some": "context"})

    assert inner.received_context == {"some": "context"}


@pytest.mark.asyncio
async def test_emergency_stop_gate_blocks_submission_through_the_full_pipeline() -> None:
    """End-to-end: with the gate wired into the pipeline exactly as
    run_st_a2_demo.py wires it, an active emergency stop must reject the
    intent before the adapter (and therefore the broker) is ever reached."""
    adapter = _CountingAdapter()
    gate = EmergencyStopRiskGate(
        AllowAllRiskGate(),
        state_loader=lambda: {"emergency_stop": {"active": True, "reason": "manual pause"}},
    )
    pipeline = CanonicalExecutionPipeline(mode="demo", risk_gate=gate, adapter=adapter)

    async def workload(active_pipeline: CanonicalExecutionPipeline) -> None:
        result = await active_pipeline.submit(_intent())
        assert result.status == "REJECTED"

    await pipeline.run(_context(), workload)

    assert adapter.calls == 0
    rejection = next(e for e in pipeline.events if e.event_type == "risk_decision")
    assert rejection.approved is False
    assert rejection.reason == "emergency stop active"


@pytest.mark.asyncio
async def test_emergency_stop_gate_allows_submission_when_inactive() -> None:
    adapter = _CountingAdapter()
    gate = EmergencyStopRiskGate(
        AllowAllRiskGate(),
        state_loader=lambda: {"emergency_stop": {"active": False}},
    )
    pipeline = CanonicalExecutionPipeline(mode="demo", risk_gate=gate, adapter=adapter)

    async def workload(active_pipeline: CanonicalExecutionPipeline) -> None:
        result = await active_pipeline.submit(_intent())
        assert result.status == "SUBMITTED"

    await pipeline.run(_context(), workload)

    assert adapter.calls == 1
