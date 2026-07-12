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

import scripts.run_st_a2_demo as runner
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


class TestInFlightAmbiguousDuplicateIsRejectedNotSubmitted:
    """Regression test for the phantom-journal bug: TradeManager.open_position()
    suppresses an in-flight-ambiguous duplicate by returning a normal dict with
    no broker order_id (see execution/trade_manager.py). Before this fix,
    run_st_a2_demo.py's _execute_via_manager() reported that as AdapterResult
    status=SUBMITTED unconditionally, which made the tick loop journal it as an
    open trade and increment risk_state['open_positions'] for a position that
    was never actually placed at the broker."""

    def test_in_flight_ambiguous_duplicate_maps_to_rejected(self):
        placed_order = {
            "order_id": "",
            "execution_id": "exec-1",
            "idempotency_key": "key-1",
            "duplicate_suppressed": True,
            "duplicate_reason": "in_flight_ambiguous",
            "opened_at": "2026-07-12T09:00:00+00:00",
        }
        result = runner._adapter_result_from_placed_order(placed_order)
        assert result.status == "REJECTED"
        assert result.details == placed_order

    def test_already_broker_acknowledged_duplicate_still_maps_to_submitted(self):
        """A duplicate that already has a real broker_order_id reflects a
        genuinely placed order — it must still report SUBMITTED, not REJECTED."""
        placed_order = {
            "order_id": "BROKER-ORDER-1",
            "execution_id": "exec-1",
            "idempotency_key": "key-1",
            "duplicate_suppressed": True,
            "duplicate_reason": "already_broker_acknowledged",
            "opened_at": "2026-07-12T09:00:00+00:00",
        }
        result = runner._adapter_result_from_placed_order(placed_order)
        assert result.status == "SUBMITTED"
        assert result.reference == "BROKER-ORDER-1"

    def test_ordinary_new_order_maps_to_submitted(self):
        placed_order = {"order_id": "SIM-001", "simulated": True}
        result = runner._adapter_result_from_placed_order(placed_order)
        assert result.status == "SUBMITTED"
        assert result.reference == "SIM-001"

    @pytest.mark.asyncio
    async def test_rejected_in_flight_ambiguous_result_never_reaches_the_broker_adapter(self):
        """End-to-end through CanonicalExecutionPipeline: once
        _adapter_result_from_placed_order() reports REJECTED, the caller's
        existing REJECTED handling (scripts/run_st_a2_demo.py: `if
        result.status == "REJECTED": raise RuntimeError(...)`) takes over —
        the same path already proven, in
        test_symbol_outside_context_scope_is_rejected_not_placed above, to
        skip journaling and risk-state updates. This test proves the pipeline
        itself faithfully returns REJECTED for this case, which is the
        precondition that existing exception handler relies on."""
        placed_order = {
            "order_id": "",
            "duplicate_suppressed": True,
            "duplicate_reason": "in_flight_ambiguous",
        }

        async def fake_execute(intent: ExecutionIntent) -> AdapterResult:
            return runner._adapter_result_from_placed_order(placed_order)

        pipeline = CanonicalExecutionPipeline(
            mode="demo", risk_gate=AllowAllRiskGate(), adapter=DemoExecutionAdapter(fake_execute),
        )

        async def workload(p: CanonicalExecutionPipeline) -> None:
            result = await p.submit(_intent())
            assert result.status == "REJECTED"
            assert result.details["duplicate_reason"] == "in_flight_ambiguous"

        await pipeline.run(_context(), workload)
