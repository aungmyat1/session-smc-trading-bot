"""Tests for adaptive/execution/demo_executor.py"""

import pytest
from adaptive.strategies import AdaptiveSignal
from adaptive.execution.demo_executor import DemoExecutor


def _signal() -> AdaptiveSignal:
    return AdaptiveSignal(
        strategy="smc_session",
        pair="EURUSD",
        direction="LONG",
        entry_price=1.1000,
        sl_price=1.0950,
        tp_price=1.1150,
        session="london",
        timestamp="2026-06-24T07:30:00+00:00",
        reason="test",
    )


class TestDemoExecutor:
    def test_dry_run_true_by_default(self):
        ex = DemoExecutor(dry_run=True)
        assert ex.dry_run is True

    @pytest.mark.asyncio
    async def test_execute_returns_simulated_status(self):
        ex = DemoExecutor(dry_run=True)
        result = await ex.execute(_signal())
        assert result["status"] == "simulated"

    @pytest.mark.asyncio
    async def test_execute_dry_run_flag_in_result(self):
        ex = DemoExecutor(dry_run=True)
        result = await ex.execute(_signal())
        assert result["dry_run"] is True

    @pytest.mark.asyncio
    async def test_execute_result_fields(self):
        ex = DemoExecutor(dry_run=True)
        result = await ex.execute(_signal())
        for key in (
            "order_id",
            "dry_run",
            "symbol",
            "direction",
            "entry",
            "sl",
            "tp",
            "timestamp",
            "status",
        ):
            assert key in result, f"Missing: {key}"

    @pytest.mark.asyncio
    async def test_execute_correct_symbol(self):
        ex = DemoExecutor(dry_run=True)
        result = await ex.execute(_signal())
        assert result["symbol"] == "EURUSD"
        assert result["direction"] == "LONG"

    @pytest.mark.asyncio
    async def test_live_mode_raises(self):
        ex = DemoExecutor(dry_run=False)
        with pytest.raises(NotImplementedError):
            await ex.execute(_signal())
