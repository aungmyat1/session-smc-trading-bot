from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from production.engine.execution_pipeline import (
    AdapterResult,
    CallbackExecutionAdapter,
    CanonicalExecutionPipeline,
    DemoExecutionAdapter,
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
