"""
Root-level test isolation, applied to the whole suite.

Defends scripts/run_st_a2_demo.py's module-level, non-injectable durable-
storage globals against test pollution of the *real*, live-deployed runner's
files/database rows (2026-07-06 incident — see
docs/systems/system2/DASHBOARD_READINESS.md §14). Three confirmed instances
of the same root cause, found by actually running the full suite and
inspecting the live host, not by code review alone:

1. `_rps_store = RiskPortfolioStore()` — a singleton with no constructor
   seam. Without isolation, any test exercising _load_risk_state()/
   _save_risk_state()/_load_portfolio_state()/_save_portfolio_state()
   (directly, via run()/_tick(), or via anything importing this module)
   upserts into the real Postgres row the live runner reads on restart.
   Confirmed: a full-suite run left 2 rows in a table that had existed for
   seconds.
2. `_STATE_PATH`/`_RISK_STATE_PATH`/`_PORTFOLIO_STATE_PATH` — hardcoded
   `Path("logs") / "..."` module constants. `tests/execution/
   test_emergency_stop_integration.py` called `runner._tick()` directly
   without monkeypatching these, and **overwrote the real, live-deployed
   runner's own `logs/strategy_demo_state.json`** with the test's fake
   `{"id": "POS-1"}` / emergency-stop-active fixture data — the most
   dangerous of the three, since it clobbered the actual runtime state a
   human operator or automated system could have read mid-test. It
   self-healed only because the real runner's next 60s tick overwrote it
   again before anyone observed the corruption.

Both are now defended here, at the suite root, so no test location — present
or future — is exempt regardless of which directory it lives in or whether
it remembers to patch these itself. A test's own explicit
`monkeypatch.setattr(runner, "_STATE_PATH", ...)` still works normally and
takes precedence for that test (monkeypatch layers correctly: last call
wins, original value restored at teardown either way) — this fixture only
supplies a safe *default* for tests that don't set one.

3. `_validation_session_mgr = ValidationSessionManager()` — same
   module-level-singleton shape as `_rps_store` (Demo Validation Mode,
   2026-07-06), added proactively this time rather than after a pollution
   incident: any test that calls `run()`/`_tick()` with
   `mode="demo_validation"` would otherwise write a real
   `operations.validation_session` row.

The module is only patched if already imported (or importable) — this
fixture does not force every test file in the suite to pay the import cost
of scripts.run_st_a2_demo if it never touches it.
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest


@pytest.fixture(autouse=True)
def _isolate_run_st_a2_demo_globals(tmp_path, monkeypatch):
    # Pytest imports every collected test module before running any test, so
    # by the time a test executes, scripts.run_st_a2_demo is already in
    # sys.modules if *any* test file (this one or another collected in the
    # same session) imports it — checking here (rather than importing
    # unconditionally) avoids paying that import cost for a narrow/targeted
    # run that never touches it at all.
    runner = sys.modules.get("scripts.run_st_a2_demo")
    if runner is None:
        yield None
        return

    # Safe defaults for the three hardcoded file paths — a test's own
    # explicit monkeypatch.setattr on these (several already have one, with
    # their own tmp_path) simply overrides this afterward, per monkeypatch's
    # normal last-write-wins semantics.
    monkeypatch.setattr(runner, "_STATE_PATH", tmp_path / "strategy_demo_state.json")
    monkeypatch.setattr(runner, "_RISK_STATE_PATH", tmp_path / "risk_state.json")
    monkeypatch.setattr(runner, "_PORTFOLIO_STATE_PATH", tmp_path / "portfolio_state.json")

    stub = MagicMock()
    stub.load_risk_state.return_value = None
    stub.load_portfolio_state.return_value = None
    stub.save_risk_state.return_value = None
    stub.save_portfolio_state.return_value = None
    monkeypatch.setattr(runner, "_rps_store", stub)

    validation_stub = MagicMock()
    validation_stub.start.return_value = "val-test-stub"
    validation_stub.resume.return_value = None
    validation_stub.active_session.return_value = None
    validation_stub.end.return_value = None
    monkeypatch.setattr(runner, "_validation_session_mgr", validation_stub)

    yield stub


@pytest.fixture
def sample_decomposition_rows() -> list[dict]:
    return [
        {
            "trade_id": "t1",
            "symbol": "GBPUSD",
            "entry_time": "2025-01-01T08:00:00Z",
            "exit_time": "2025-01-01T12:00:00Z",
            "gross_pnl": 2.0,
            "spread_cost": 0.1,
            "commission_cost": 0.05,
            "slippage_cost": 0.0,
            "net_pnl": 1.85,
            "market_regime": "TREND_HIGH_VOL",
            "session": "new_york",
        },
        {
            "trade_id": "t2",
            "symbol": "GBPUSD",
            "entry_time": "2025-01-02T08:00:00Z",
            "exit_time": "2025-01-02T10:00:00Z",
            "gross_pnl": 1.0,
            "spread_cost": 0.1,
            "commission_cost": 0.05,
            "slippage_cost": 0.0,
            "net_pnl": 0.85,
            "market_regime": "RANGE_HIGH_VOL",
            "session": "london",
        },
        {
            "trade_id": "t3",
            "symbol": "XAUUSD",
            "entry_time": "2025-02-01T08:00:00Z",
            "exit_time": "2025-02-01T09:00:00Z",
            "gross_pnl": -1.0,
            "spread_cost": 0.2,
            "commission_cost": 0.0,
            "slippage_cost": 0.0,
            "net_pnl": -1.2,
            "market_regime": "RANGE_LOW_VOL",
            "session": "london",
        },
        {
            "trade_id": "t4",
            "symbol": "XAUUSD",
            "entry_time": "2025-02-02T08:00:00Z",
            "exit_time": "2025-02-02T09:00:00Z",
            "gross_pnl": -1.0,
            "spread_cost": 0.2,
            "commission_cost": 0.0,
            "slippage_cost": 0.0,
            "net_pnl": -1.2,
            "market_regime": "RANGE_LOW_VOL",
            "session": "london",
        },
    ]
