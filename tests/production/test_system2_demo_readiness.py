"""System 2 first-wave acceptance coverage; no broker or live-capital access."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from production.engine.execution_pipeline import (
    AdapterResult,
    CanonicalExecutionPipeline,
    DemoExecutionAdapter,
    ExecutionIntent,
    RiskDecision,
)
from production.engine.runtime import RuntimeAuthority, RuntimeContext
from production.api import ProductionReadAPI
from shared.serialization import append_jsonl, write_json
from shared.strategy_package import build_canonical_package

PRIVATE_KEY = "11" * 32
PUBLIC_KEY = "d04ab232742bb4ab3a1368bd4615e4e6d0224ab71a016baf8520a332c9778737"


def _package(tmp_path: Path) -> str:
    return build_canonical_package(
        tmp_path / "system2-readiness.tar.gz",
        strategy_id="SYSTEM2-FIXTURE",
        strategy_version="1.0.0",
        adapter_id="FixtureAdapter",
        adapter_version="1.0.0",
        strategy_spec="# Synthetic System 2 readiness fixture\n",
        parameters={"symbols": ["EURUSD"], "timeframes": ["M15"]},
        risk_policy={"policy_id": "paper-only", "live_trading_enabled": False},
        evidence={"trust": "SYNTHETIC", "purpose": "system2-readiness"},
        approval={
            "decision": "APPROVED",
            "approved_at": "2026-01-01T00:00:00+00:00",
            "expires_at": "2099-01-01T00:00:00+00:00",
            "revoked": False,
        },
        signing_key=PRIVATE_KEY,
    ).archive_path


class _RiskGate:
    def __init__(self, approved: bool) -> None:
        self.approved = approved

    def evaluate(self, _intent: ExecutionIntent) -> RiskDecision:
        return RiskDecision(self.approved, "APPROVED" if self.approved else "RISK_FIREWALL_REJECTED")


def _intent() -> ExecutionIntent:
    return ExecutionIntent(
        "fixture-intent",
        "SYSTEM2-FIXTURE",
        "EURUSD",
        "buy",
        0.01,
        stop_loss=1.09,
        take_profit=1.11,
    )


@pytest.mark.asyncio
async def test_valid_package_starts_executes_paper_order_and_journals_decisions(tmp_path: Path) -> None:
    journal = tmp_path / "execution-decisions.jsonl"
    execute = AsyncMock(return_value=AdapterResult("FILLED", "paper-order-1", {"simulated": True}))
    authority = RuntimeAuthority(root=tmp_path, package_path=_package(tmp_path), verifying_public_key=PUBLIC_KEY)

    def pipeline_factory(_context: RuntimeContext) -> CanonicalExecutionPipeline:
        return CanonicalExecutionPipeline(
            mode="demo",
            risk_gate=_RiskGate(True),
            adapter=DemoExecutionAdapter(execute),
            package_validator=authority.revalidate_package,
            event_sink=lambda event: append_jsonl(journal, event.to_dict()),
        )

    async def workload(pipeline: CanonicalExecutionPipeline) -> None:
        result = await pipeline.submit(_intent())
        assert result.status == "FILLED"
        assert result.details["simulated"] is True

    await authority.run_pipeline(pipeline_factory, workload)

    execute.assert_awaited_once_with(_intent())
    records = [json.loads(line) for line in journal.read_text(encoding="utf-8").splitlines()]
    assert [record["event_type"] for record in records] == [
        "pipeline_started",
        "intent_received",
        "risk_decision",
        "execution_result",
        "pipeline_stopped",
    ]
    assert next(record for record in records if record["event_type"] == "risk_decision")["approved"] is True


@pytest.mark.asyncio
async def test_risk_rejection_is_journaled_and_never_reaches_demo_adapter(tmp_path: Path) -> None:
    journal = tmp_path / "execution-decisions.jsonl"
    execute = AsyncMock(return_value=AdapterResult("FILLED", "must-not-run"))
    context = RuntimeContext(
        "owner", "/fixture", "package", "sha", "SYSTEM2-FIXTURE", "1.0.0",
        ("EURUSD",), "vantage-demo", "demo-risk-firewall",
    )
    pipeline = CanonicalExecutionPipeline(
        mode="demo",
        risk_gate=_RiskGate(False),
        adapter=DemoExecutionAdapter(execute),
        event_sink=lambda event: append_jsonl(journal, event.to_dict()),
    )

    async def workload(active: CanonicalExecutionPipeline) -> None:
        result = await active.submit(_intent())
        assert result.status == "REJECTED"

    await pipeline.run(context, workload)
    execute.assert_not_awaited()
    records = [json.loads(line) for line in journal.read_text(encoding="utf-8").splitlines()]
    decision = next(record for record in records if record["event_type"] == "risk_decision")
    assert decision["approved"] is False
    assert decision["reason"] == "RISK_FIREWALL_REJECTED"


def test_runtime_dashboard_status_is_read_only_and_package_scoped(tmp_path: Path) -> None:
    state = {
        "state": "STOPPED",
        "package_id": "fixture-package",
        "package_sha256": "a" * 64,
        "strategy_id": "SYSTEM2-FIXTURE",
        "strategy_version": "1.0.0",
    }
    write_json(tmp_path / "data/production/runtime/runtime-state.json", state)

    class Repository:
        def list_records(self, _record_type: str, *, limit: int = 100):
            return []

    class Observability:
        def health(self):
            return {"status": "PASS", "live_trading": False}

        def metrics(self):
            return "agtrade_broker_writes_enabled 0\n"

    api = ProductionReadAPI(Repository(), Observability(), root=tmp_path)
    assert api.status()["runtime"]["state"] == "STOPPED"
    assert api.package() == {
        "package_id": "fixture-package",
        "package_sha256": "a" * 64,
        "strategy_id": "SYSTEM2-FIXTURE",
        "strategy_version": "1.0.0",
    }
    assert "agtrade_broker_writes_enabled 0" in api.metrics()
