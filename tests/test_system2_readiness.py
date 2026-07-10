"""
Tests for System 2's fail-closed readiness aggregator
(dashboard/status_server.py::_system2_readiness()) and its two new endpoints:
  GET /api/system2/readiness  (JSON)
  GET /system2/readiness      (server-rendered HTML)

See docs/systems/system2/DASHBOARD_READINESS.md for what each of the 10 checks
means and what conditions produce READY vs NOT_READY.

Convention follows tests/test_status_server.py: monkeypatch status_server.ROOT
and dashboard.control_state.CONTROL_STATE_PATH to a tmp_path, write minimal
state files, and use FastAPI's TestClient for HTTP-level tests. Unit tests of
the aggregation logic itself mock out the heavier collaborators
(_health_summary, db_health_check, _duplicate_runtime_check) so each check's
fail-closed behavior can be tested in isolation, matching this file's own
never-default-to-ok contract.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi.testclient import TestClient

import dashboard.control_state as control_state
import dashboard.status_server as status_server


def _write(path: Path, content) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content if isinstance(content, str) else json.dumps(content), encoding="utf-8")


_ALL_OK_HEALTH = {
    "score": 100,
    "checks": {
        "runner_state": "running",
        "broker_connected": True,
        "last_tick_fresh": True,
        "emergency_stop_active": False,
        "reconciliation_status": "in_sync",
        "governance_allowed": True,
        "trading_allowed": True,
        "open_positions": 0,
        "closed_trades": 0,
    },
    "governance": {},
    "trading_permission": {"mode": "NORMAL", "trading_allowed": True},
    "updated_at": "2026-07-05T00:00:00+00:00",
}


def _ok_db() -> dict:
    return {"reachable": True, "configured": True, "latency_ms": 1.0, "error": None}


def _ok_dup() -> dict:
    return {"known": True, "process_count": 1, "no_duplicate": True}


def _base_env(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(status_server, "ROOT", tmp_path)
    monkeypatch.setattr(control_state, "CONTROL_STATE_PATH", tmp_path / "reports" / "control_state.json")
    _write(
        tmp_path / "logs" / "strategy_demo_state.json",
        {
            "strategy": "ST-A2", "status": "running", "broker_status": "connected",
            "last_tick_at": "2026-07-05T00:00:00+00:00", "open_positions": [], "pairs": ["EURUSD"],
        },
    )
    _write(tmp_path / "logs" / "risk_state.json", {"halted": False})
    _write(tmp_path / "logs" / "portfolio_state.json", {"daily_pnl_pct": 0.0, "open_symbols": []})
    _write(
        tmp_path / "config" / "strategy_catalog.yaml",
        "strategies:\n  ST-A2:\n    approved: true\n    status: PRODUCTION\n",
    )
    control_state.save_control_state({})  # known-good control state file on disk


def _patch_collaborators(monkeypatch, *, health=None, db=None, dup=None) -> None:
    monkeypatch.setattr(status_server, "_health_summary", lambda: health or _ALL_OK_HEALTH)
    monkeypatch.setattr(status_server, "db_health_check", lambda: db or _ok_db())
    monkeypatch.setattr(status_server, "_duplicate_runtime_check", lambda **_: dup or _ok_dup())


# ── Unit tests: readiness aggregation ─────────────────────────────────────────

def test_all_checks_pass_yields_ready(tmp_path, monkeypatch):
    _base_env(tmp_path, monkeypatch)
    _patch_collaborators(monkeypatch)

    result = status_server._system2_readiness()

    assert result["ready"] is True
    assert result["status"] == "READY"
    assert result["blocking_reasons"] == []
    assert len(result["checks"]) == 10


def test_unapproved_strategy_blocks_readiness(tmp_path, monkeypatch):
    _base_env(tmp_path, monkeypatch)
    _write(
        tmp_path / "config" / "strategy_catalog.yaml",
        "strategies:\n  ST-A2:\n    approved: false\n    status: DEFERRED_REVALIDATION\n",
    )
    _patch_collaborators(monkeypatch)

    result = status_server._system2_readiness()

    assert result["ready"] is False
    assert "strategy_package_approved" in result["blocking_reasons"]
    assert result["checks"]["strategy_package_approved"]["detail"]["approved"] is False
    assert result["checks"]["strategy_package_approved"]["detail"]["svos_status"] == "DEFERRED_REVALIDATION"


def test_risk_state_missing_fails_risk_firewall_check(tmp_path, monkeypatch):
    _base_env(tmp_path, monkeypatch)
    (tmp_path / "logs" / "risk_state.json").unlink()
    _patch_collaborators(monkeypatch)

    result = status_server._system2_readiness()

    assert result["ready"] is False
    assert "risk_firewall_active" in result["blocking_reasons"]


# ── Fail-closed behavior ───────────────────────────────────────────────────────

def test_database_unreachable_fails_closed(tmp_path, monkeypatch):
    _base_env(tmp_path, monkeypatch)
    _patch_collaborators(
        monkeypatch,
        db={"reachable": False, "configured": True, "latency_ms": None, "error": "connection refused"},
    )

    result = status_server._system2_readiness()

    assert result["ready"] is False
    assert "database_reachable" in result["blocking_reasons"]


def test_database_not_configured_fails_closed_not_skipped(tmp_path, monkeypatch):
    """No DATABASE_URL must NOT be silently treated as 'not applicable' — it's
    still a failing check under fail-closed semantics."""
    _base_env(tmp_path, monkeypatch)
    _patch_collaborators(
        monkeypatch,
        db={"reachable": False, "configured": False, "latency_ms": None, "error": "DATABASE_URL not configured"},
    )

    result = status_server._system2_readiness()

    assert result["ready"] is False
    assert "database_reachable" in result["blocking_reasons"]


def test_missing_control_state_file_fails_emergency_stop_known(tmp_path, monkeypatch):
    _base_env(tmp_path, monkeypatch)
    # Point at a control-state path that is never created.
    monkeypatch.setattr(control_state, "CONTROL_STATE_PATH", tmp_path / "reports" / "never_created.json")
    _patch_collaborators(monkeypatch)

    result = status_server._system2_readiness()

    assert result["ready"] is False
    assert "emergency_stop_known" in result["blocking_reasons"]


def test_corrupt_control_state_file_fails_emergency_stop_known(tmp_path, monkeypatch):
    _base_env(tmp_path, monkeypatch)
    (tmp_path / "reports" / "control_state.json").write_text("{not valid json", encoding="utf-8")
    _patch_collaborators(monkeypatch)

    result = status_server._system2_readiness()

    assert result["ready"] is False
    assert "emergency_stop_known" in result["blocking_reasons"]


def test_duplicate_runtime_detected_fails_closed(tmp_path, monkeypatch):
    _base_env(tmp_path, monkeypatch)
    _patch_collaborators(monkeypatch, dup={"known": True, "process_count": 2, "no_duplicate": False})

    result = status_server._system2_readiness()

    assert result["ready"] is False
    assert "no_duplicate_runtime" in result["blocking_reasons"]
    assert result["checks"]["no_duplicate_runtime"]["detail"]["process_count"] == 2


def test_duplicate_runtime_unknown_fails_closed_not_open(tmp_path, monkeypatch):
    """An undeterminable process count must NOT default to 'assume fine' —
    unknown fails closed, same as every other check in this aggregator."""
    _base_env(tmp_path, monkeypatch)
    _patch_collaborators(
        monkeypatch, dup={"known": False, "process_count": None, "no_duplicate": False, "error": "boom"}
    )

    result = status_server._system2_readiness()

    assert result["ready"] is False
    assert "no_duplicate_runtime" in result["blocking_reasons"]


def test_reconciliation_unknown_status_fails_closed(tmp_path, monkeypatch):
    _base_env(tmp_path, monkeypatch)
    control_state.save_control_state({"reconciliation": {"status": "unknown"}})
    _patch_collaborators(monkeypatch)

    result = status_server._system2_readiness()

    assert result["ready"] is False
    assert "reconciliation_available" in result["blocking_reasons"]


def test_reconciliation_explicitly_unavailable_does_not_block(tmp_path, monkeypatch):
    """Per the task's carve-out: reconciliation must be *available* OR
    *explicitly marked unavailable* — an explicit 'unavailable' status is a
    known, honest answer and must not itself block readiness."""
    _base_env(tmp_path, monkeypatch)
    control_state.save_control_state({"reconciliation": {"status": "unavailable"}})
    _patch_collaborators(monkeypatch)

    result = status_server._system2_readiness()

    assert "reconciliation_available" not in result["blocking_reasons"]


def test_broker_disconnected_but_not_explicitly_disabled_fails_closed(tmp_path, monkeypatch):
    _base_env(tmp_path, monkeypatch)
    unhealthy = json.loads(json.dumps(_ALL_OK_HEALTH))
    unhealthy["checks"]["broker_connected"] = False
    _patch_collaborators(monkeypatch, health=unhealthy)

    result = status_server._system2_readiness()

    assert result["ready"] is False
    assert "broker_reachable_or_disabled" in result["blocking_reasons"]


def test_broker_explicitly_disabled_read_only_mode_passes(tmp_path, monkeypatch):
    """Per the task's carve-out: broker must be reachable OR explicitly
    disabled in read-only mode — the latter is a deliberate, known state."""
    _base_env(tmp_path, monkeypatch)
    _write(
        tmp_path / "logs" / "strategy_demo_state.json",
        {
            "strategy": "ST-A2", "status": "running", "broker_status": "disabled",
            "last_tick_at": "2026-07-05T00:00:00+00:00", "open_positions": [], "pairs": ["EURUSD"],
        },
    )
    unhealthy = json.loads(json.dumps(_ALL_OK_HEALTH))
    unhealthy["checks"]["broker_connected"] = False
    _patch_collaborators(monkeypatch, health=unhealthy)

    result = status_server._system2_readiness()

    assert "broker_reachable_or_disabled" not in result["blocking_reasons"]


# ── Stale heartbeat ────────────────────────────────────────────────────────────

def test_stale_heartbeat_fails_closed(tmp_path, monkeypatch):
    _base_env(tmp_path, monkeypatch)
    stale = json.loads(json.dumps(_ALL_OK_HEALTH))
    stale["checks"]["last_tick_fresh"] = False
    _patch_collaborators(monkeypatch, health=stale)

    result = status_server._system2_readiness()

    assert result["ready"] is False
    assert "heartbeat_fresh" in result["blocking_reasons"]


def test_fresh_heartbeat_does_not_block(tmp_path, monkeypatch):
    _base_env(tmp_path, monkeypatch)
    _patch_collaborators(monkeypatch)

    result = status_server._system2_readiness()

    assert "heartbeat_fresh" not in result["blocking_reasons"]


# ── Emergency stop visibility ──────────────────────────────────────────────────

def test_active_emergency_stop_is_visible_and_blocks_readiness(tmp_path, monkeypatch):
    _base_env(tmp_path, monkeypatch)
    control_state.activate_emergency_stop(
        reason="test halt", activated_by="tester", scope="block_only", source="test"
    )
    emergency = json.loads(json.dumps(_ALL_OK_HEALTH))
    emergency["checks"]["emergency_stop_active"] = True
    emergency["checks"]["trading_allowed"] = False  # TradingPermissionService folds this in for real
    _patch_collaborators(monkeypatch, health=emergency)

    result = status_server._system2_readiness()

    # The state must be visible (known) even though it blocks readiness —
    # "known" and "not blocking" are different questions.
    assert result["checks"]["emergency_stop_known"]["ok"] is True
    assert result["checks"]["emergency_stop_known"]["detail"]["active"] is True
    assert result["ready"] is False
    assert "runtime_authority_valid" in result["blocking_reasons"]


def test_inactive_emergency_stop_is_visible_and_does_not_block(tmp_path, monkeypatch):
    _base_env(tmp_path, monkeypatch)
    _patch_collaborators(monkeypatch)

    result = status_server._system2_readiness()

    assert result["checks"]["emergency_stop_known"]["ok"] is True
    assert result["checks"]["emergency_stop_known"]["detail"]["active"] is False
    assert "emergency_stop_known" not in result["blocking_reasons"]


# ── No live trading is enabled by this change ─────────────────────────────────

def test_readiness_read_only_reports_but_never_alters_trading_mode(tmp_path, monkeypatch):
    """This aggregator is read-only: it must never set LIVE_TRADING/DEMO_ONLY
    or any trading setting, only report whatever is already configured."""
    _base_env(tmp_path, monkeypatch)
    monkeypatch.setenv("LIVE_TRADING", "false")
    monkeypatch.setenv("DEMO_ONLY", "true")
    _patch_collaborators(monkeypatch)
    env_before = dict(os.environ)

    result = status_server._system2_readiness()

    assert dict(os.environ) == env_before  # no mutation of the environment
    assert result["mode"]["live_trading"] is False
    assert result["mode"]["demo_only"] is True
    assert result["mode"]["label"] != "LIVE"


def test_readiness_mode_reflects_live_trading_true_without_enabling_it(tmp_path, monkeypatch):
    """Even if LIVE_TRADING=true were somehow set elsewhere, this endpoint must
    only *report* that fact via os.environ.get (read), never set it — and must
    not itself flip DEMO_ONLY back to true or otherwise mutate the environment
    just because it observed a live-trading-flagged environment."""
    _base_env(tmp_path, monkeypatch)
    monkeypatch.setenv("LIVE_TRADING", "true")
    monkeypatch.setenv("DEMO_ONLY", "false")
    _patch_collaborators(monkeypatch)
    env_before = dict(os.environ)

    result = status_server._system2_readiness()

    assert dict(os.environ) == env_before  # still no mutation, even in this branch
    assert result["mode"]["live_trading"] is True
    assert result["mode"]["label"] == "LIVE"


def test_new_endpoints_are_get_only_no_write_surface(tmp_path, monkeypatch):
    """Confirms the new readiness surface exposes no POST/mutation route that
    could be used to flip live trading or any other setting."""
    _base_env(tmp_path, monkeypatch)
    _patch_collaborators(monkeypatch)
    client = TestClient(status_server.app)

    assert client.post("/api/system2/readiness").status_code == 405
    assert client.post("/system2/readiness").status_code == 405
    assert client.put("/api/system2/readiness").status_code == 405
    assert client.delete("/api/system2/readiness").status_code == 405


# ── API tests: new dashboard endpoints ─────────────────────────────────────────

def test_api_system2_readiness_returns_expected_shape(tmp_path, monkeypatch):
    _base_env(tmp_path, monkeypatch)
    _patch_collaborators(monkeypatch)
    client = TestClient(status_server.app)

    response = client.get("/api/system2/readiness")

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) >= {"ready", "status", "blocking_reasons", "mode", "checks", "generated_at"}
    assert len(body["checks"]) == 10
    expected_checks = {
        "database_reachable", "runtime_authority_valid", "strategy_package_approved",
        "risk_firewall_active", "broker_reachable_or_disabled", "emergency_stop_known",
        "no_critical_incident", "heartbeat_fresh", "no_duplicate_runtime", "reconciliation_available",
    }
    assert set(body["checks"].keys()) == expected_checks


def test_api_system2_readiness_reports_not_ready_for_unapproved_strategy(tmp_path, monkeypatch):
    """End-to-end HTTP check that the real, currently-deployed ST-A2 config
    (approved: false, DEFERRED_REVALIDATION) is reported honestly."""
    _base_env(tmp_path, monkeypatch)
    _write(
        tmp_path / "config" / "strategy_catalog.yaml",
        "strategies:\n  ST-A2:\n    approved: false\n    status: DEFERRED_REVALIDATION\n",
    )
    _patch_collaborators(monkeypatch)
    client = TestClient(status_server.app)

    response = client.get("/api/system2/readiness")

    assert response.status_code == 200
    body = response.json()
    assert body["ready"] is False
    assert "strategy_package_approved" in body["blocking_reasons"]


def test_system2_readiness_html_page_renders_all_panels(tmp_path, monkeypatch):
    from unittest.mock import patch

    _base_env(tmp_path, monkeypatch)
    _patch_collaborators(monkeypatch)
    fake_snapshot = {
        "positions": {"items": [], "count": 0}, "orders": {},
    }
    client = TestClient(status_server.app)

    with patch.object(status_server.live_dashboard_service, "load_snapshot", return_value=fake_snapshot), \
         patch.object(status_server, "get_recent_events", return_value=[]):
        response = client.get("/system2/readiness")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    for expected in (
        "System 2", "Readiness Summary", "Broker Connection", "Strategy Package",
        "Risk Firewall", "Emergency Stop", "Database Health", "Open Positions",
        "Order Lifecycle Timeline", "Recent Events",
    ):
        assert expected in response.text


def test_system2_readiness_html_handles_empty_positions_and_orders_gracefully(tmp_path, monkeypatch):
    from unittest.mock import patch

    _base_env(tmp_path, monkeypatch)
    _patch_collaborators(monkeypatch)
    client = TestClient(status_server.app)

    with patch.object(status_server.live_dashboard_service, "load_snapshot", return_value={}), \
         patch.object(status_server, "get_recent_events", return_value=[]):
        response = client.get("/system2/readiness")

    assert response.status_code == 200
    assert "No open positions." in response.text
    assert "No recent orders." in response.text
    assert "No recent events." in response.text
