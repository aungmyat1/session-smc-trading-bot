"""
Verifies the Sprint 2.1 (SYSTEM2_MASTER_PLAN.md Phase 2) wiring: order
placement in scripts/run_st_a2_demo.py now flows through
production.engine.CanonicalExecutionPipeline instead of calling
TradeManager.open_position() directly. Mirrors the exact pipeline/context
shape run_st_a2_demo.run() constructs, without needing the full _tick()
market-data/strategy fixture chain.
"""

from __future__ import annotations

import pytest

from production.engine import AdapterResult, AllowAllRiskGate, CanonicalExecutionPipeline, DemoExecutionAdapter, ExecutionIntent
from production.engine.runtime import RuntimeContext


def _context(**overrides) -> RuntimeContext:
    fields = dict(
        owner_id="run_st_a2_demo", package_path="", package_id="", package_sha256="",
        strategy_id="ST-A2", strategy_version="1.0.0", symbols=("EURUSD", "GBPUSD", "XAUUSD"),
        broker_adapter="vantage-demo", risk_enforcer="pre-approved-by-existing-tick-controls",
    )
    fields.update(overrides)
    return RuntimeContext(**fields)


def _intent(**overrides) -> ExecutionIntent:
    fields = dict(intent_id="ST-A2:EURUSD:t1", strategy_id="ST-A2", symbol="EURUSD", side="BUY", quantity=0.10)
    fields.update(overrides)
    return ExecutionIntent(**fields)


@pytest.mark.asyncio
async def test_pipeline_passes_through_manager_order_unchanged():
    placed = {"order_id": "ORD-1", "execution_id": "exec-1", "simulated": True}

    async def fake_execute(intent: ExecutionIntent) -> AdapterResult:
        assert intent.symbol == "EURUSD"
        return AdapterResult(status="SUBMITTED", reference=placed["order_id"], details=placed)

    pipeline = CanonicalExecutionPipeline(
        mode="demo", risk_gate=AllowAllRiskGate(), adapter=DemoExecutionAdapter(fake_execute),
    )

    async def workload(p: CanonicalExecutionPipeline) -> None:
        result = await p.submit(_intent())
        assert result.status == "SUBMITTED"
        assert dict(result.details) == placed

    await pipeline.run(_context(), workload)


@pytest.mark.asyncio
async def test_symbol_outside_context_scope_is_rejected_not_placed():
    """Guards the real regression risk of this wiring: if the runner's
    RuntimeContext.symbols ever drifted from the pairs it actually trades, an
    order would be silently REJECTED instead of placed — this must be loud,
    not a silent drop, and manager.open_position() must never be called."""
    called = False

    async def fake_execute(intent: ExecutionIntent) -> AdapterResult:
        nonlocal called
        called = True
        return AdapterResult(status="SUBMITTED")

    pipeline = CanonicalExecutionPipeline(
        mode="demo", risk_gate=AllowAllRiskGate(), adapter=DemoExecutionAdapter(fake_execute),
    )

    async def workload(p: CanonicalExecutionPipeline) -> None:
        result = await p.submit(_intent(symbol="USDCHF"))
        assert result.status == "REJECTED"
        assert result.details["reason"] == "PACKAGE_SCOPE_MISMATCH"

    await pipeline.run(_context(), workload)
    assert called is False
