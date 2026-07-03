from __future__ import annotations

from datetime import datetime, timezone

import pytest

from production.engine.adapter_registry import AdapterRegistry
from production.engine.contracts import DisabledVantageAdapter, RUNTIME_API_VERSION
from production.engine.execution_pipeline import ExecutionIntent
from production.engine.orders import OrderService
from production.engine.positions import PositionService
from production.engine.risk import AccountSnapshot, MarketSnapshot, RiskContext, RiskFirewall
from production.recovery import RecoveryManager
from production.operations import EmergencyAuditSink, OperationsUnavailable, PostgresOperationsRepository
from production.reporting import OperationsReportService


POLICY = {
    "policy_id": "disabled-v1",
    "max_spread_pips": 2.0,
    "max_daily_loss": 100.0,
    "max_drawdown_percent": 10.0,
    "max_positions": 1,
    "max_risk_percent": 0.5,
    "min_free_margin": 100.0,
    "allow_weekends": True,
}


def _intent() -> ExecutionIntent:
    return ExecutionIntent("signal-1", "S", "EURUSD", "buy", 0.01, 1.09, 1.11, {"risk_percent": 0.25})


def _context(**market_changes) -> RiskContext:
    market = {"timestamp": datetime.now(timezone.utc), "spread_pips": 1.0, "latency_ms": 10.0}
    market.update(market_changes)
    return RiskContext(AccountSnapshot(10000, 10000, 9000), MarketSnapshot(**market))


def test_risk_firewall_approves_complete_safe_context_and_fails_closed() -> None:
    assert RiskFirewall(POLICY).evaluate(_intent(), _context()).approved
    assert RiskFirewall({}).evaluate(_intent(), _context()).reason == "POLICY_INCOMPLETE"
    assert RiskFirewall(POLICY).evaluate(_intent()).reason == "RISK_CONTEXT_UNAVAILABLE"
    assert RiskFirewall(POLICY).evaluate(_intent(), _context(spread_pips=5)).reason == "SPREAD_LIMIT"


@pytest.mark.asyncio
async def test_disabled_vantage_adapter_rejects_every_write_and_orders_are_idempotent() -> None:
    adapter = DisabledVantageAdapter()
    orders = OrderService(adapter)
    first = await orders.submit({"symbol": "EURUSD"}, idempotency_key="one")
    second = await orders.submit({"symbol": "EURUSD"}, idempotency_key="one")
    assert first is second
    assert first.state == "REJECTED_DISABLED"
    assert (await orders.cancel("x"))["status"] == "REJECTED_DISABLED"
    assert (await orders.modify("x", {}))["status"] == "REJECTED_DISABLED"


@pytest.mark.asyncio
async def test_position_service_enforces_one_position_per_symbol() -> None:
    positions = PositionService(OrderService(DisabledVantageAdapter()))
    result = await positions.open({"symbol": "EURUSD"}, idempotency_key="one")
    assert result.state == "REJECTED_DISABLED"
    assert positions.snapshot() == []


def test_adapter_registry_checks_version_hash_and_runtime_api() -> None:
    class Runtime:
        def on_market_event(self, event):
            return None

    registry = AdapterRegistry()
    registration = registry.register("safe", "1", lambda _: Runtime(), code_sha256="a" * 64)
    assert registry.resolve("safe", "1", registration.code_sha256, RUNTIME_API_VERSION, {})
    with pytest.raises(PermissionError, match="code hash"):
        registry.resolve("safe", "1", "b" * 64, RUNTIME_API_VERSION, {})


@pytest.mark.asyncio
async def test_recovery_stops_at_first_inconsistent_reconciliation() -> None:
    class Repo:
        def checkpoint(self, runtime_id, state):
            pass

    handlers = {step: (lambda: True) for step in RecoveryManager.STEPS}
    handlers["reconcile_orders"] = lambda: {"consistent": False}
    result = await RecoveryManager(Repo()).recover("r", handlers)
    assert not result.ready
    assert result.completed_steps[-1] == "reconcile_account"


def test_emergency_audit_is_explicitly_non_authoritative(tmp_path) -> None:
    path = tmp_path / "audit.jsonl"
    EmergencyAuditSink(path).append("database_failure", {"reason": "down"})
    assert '"authoritative": false' in path.read_text()


def test_operating_reports_are_deterministic_pairs(tmp_path) -> None:
    service = OperationsReportService(tmp_path)
    first = service.write("health", "health-1", {"status": "PASS"})
    second = service.write("health", "health-1", {"status": "PASS"})
    assert first["sha256"] == second["sha256"]
    assert (tmp_path / "health/health-1.json").exists()
    assert (tmp_path / "health/health-1.md").exists()


def test_postgres_repository_fails_closed_without_json_fallback() -> None:
    class BrokenSession:
        def execute(self, *args, **kwargs):
            raise RuntimeError("db down")

        def rollback(self):
            pass

    with pytest.raises(OperationsUnavailable):
        PostgresOperationsRepository(BrokenSession()).append_event("intent", {})
