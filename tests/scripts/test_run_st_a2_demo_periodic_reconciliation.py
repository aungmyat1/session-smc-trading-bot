"""
SYS2-T014: periodic execution-record reconciliation
(docs/systems/system2/SYS2-T014-DESIGN.md, risk-register #14).

Covers exactly the four regression areas the task specified:
  1. periodic execution   -> _should_run_periodic_reconciliation policy
  2. duplicate reconciliation -> reconcile_pending_executions() called twice
     in a row (periodic-call style) is still a safe no-op the second time
  3. timeout ambiguity preservation -> TradeManager's ambiguous-error
     classification is unchanged by this work
  4. existing startup behavior -> the one-shot startup call site (no
     min_pending_age_seconds kwarg) behaves exactly as before

Does not spin up the full broker/runtime stack (MT5Connector, Telegram,
etc.) — the tick-loop wiring itself is a thin, already-tested combination of
existing pieces (reconcile_pending_executions, TradeManager.get_positions,
OperationsRecorder.record_recovery_checkpoint), each covered by its own
existing test suite. This file isolates the two things SYS2-T014 actually
adds: the periodicity policy and the age gate's interaction with repeated
calls.
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

import scripts.run_st_a2_demo as runner
from core.trade_journal_db import TradeJournalDB
from execution.execution_state import ExecutionStateStore
from execution.startup_recovery import reconcile_pending_executions
from execution.trade_manager import TradeManager


# ── 1. Periodic execution policy ───────────────────────────────────────────

class TestShouldRunPeriodicReconciliation:
    def test_disabled_when_every_n_ticks_is_zero(self):
        assert runner._should_run_periodic_reconciliation(5, 0) is False
        assert runner._should_run_periodic_reconciliation(0, 0) is False

    def test_disabled_when_every_n_ticks_is_negative(self):
        assert runner._should_run_periodic_reconciliation(10, -1) is False

    def test_fires_on_exact_multiples(self):
        assert runner._should_run_periodic_reconciliation(5, 5) is True
        assert runner._should_run_periodic_reconciliation(10, 5) is True
        assert runner._should_run_periodic_reconciliation(15, 5) is True

    def test_does_not_fire_between_multiples(self):
        for tick_count in (1, 2, 3, 4, 6, 7, 8, 9):
            assert runner._should_run_periodic_reconciliation(tick_count, 5) is False

    def test_config_constants_are_configurable_types_with_sane_defaults(self):
        # Not a module-reload test (run_st_a2_demo.py has module-level side
        # effects like TradeJournalDB() — reloading it mid-suite would risk
        # destabilizing other tests sharing this process). Just locks in
        # that both knobs exist, are the right type, and default to
        # something reasonable (interval > 0, age gate >= 0).
        assert isinstance(runner.RECONCILE_EVERY_N_TICKS, int)
        assert isinstance(runner.RECONCILE_MIN_PENDING_AGE_S, float)
        assert runner.RECONCILE_EVERY_N_TICKS > 0
        assert runner.RECONCILE_MIN_PENDING_AGE_S >= 0.0


# ── 2. Duplicate reconciliation across repeated periodic-style calls ──────

def test_repeated_periodic_style_calls_do_not_duplicate_resolution(tmp_path):
    store = ExecutionStateStore(tmp_path)
    journal = TradeJournalDB(tmp_path / "journal.db")
    record = store.create_record(
        strategy_id="ST-A2", strategy_version="1.0.0", signal_id="sig-periodic",
        metadata={"symbol": "EURUSD", "direction": "buy", "lots": 0.01},
    )
    store.transition(record.execution_id, "RISK_APPROVED")
    store.transition(record.execution_id, "SUBMISSION_PENDING")
    store.transition(record.execution_id, "BROKER_ACKNOWLEDGED", broker_order_id="ORD-PERIODIC-1")
    positions = [{"id": "ORD-PERIODIC-1", "symbol": "EURUSD", "direction": "buy", "lots": 0.01, "entry": 1.1}]

    # Simulates two consecutive periodic-reconciliation ticks (same config
    # the runtime loop would use — RECONCILE_MIN_PENDING_AGE_S applied both times).
    first = reconcile_pending_executions(
        store, journal, positions, min_pending_age_seconds=runner.RECONCILE_MIN_PENDING_AGE_S,
    )
    second = reconcile_pending_executions(
        store, journal, positions, min_pending_age_seconds=runner.RECONCILE_MIN_PENDING_AGE_S,
    )

    assert first.recovered_count == 1
    assert second.resolved == []
    assert second.orphaned_positions == []
    assert len(journal.get_all_trades()) == 1


# ── 3. Timeout ambiguity preservation ──────────────────────────────────────

@pytest.mark.asyncio
async def test_timeout_still_classified_ambiguous_and_parked_recovery_pending(tmp_path):
    """SYS2-T014 touches execution/startup_recovery.py and the tick loop
    only — execution/trade_manager.py's ambiguous-error classification
    (`_classify_error`, `:196-200`) must be provably unchanged."""
    from types import SimpleNamespace

    executor = MagicMock()
    executor.place_order = AsyncMock(side_effect=RuntimeError("timeout"))
    store = ExecutionStateStore(tmp_path)
    mgr = TradeManager(executor, execution_store=store)
    signal = SimpleNamespace(
        pair="EURUSD", side="long", entry=1.1000, stop_loss=1.0950, take_profit=1.1150,
    )

    with pytest.raises(RuntimeError):
        await mgr.open_position(signal, 0.02)

    incomplete = store.recover_incomplete()
    assert len(incomplete) == 1
    assert incomplete[0].state == "RECOVERY_PENDING"
    assert incomplete[0].broker_order_id == ""  # no evidence the order reached the broker


# ── 4. Existing (pre-SYS2-T014) startup behavior unchanged ────────────────

def test_startup_call_site_signature_unchanged():
    """The startup-recovery call site (scripts/run_st_a2_demo.py, inside
    run()) predates SYS2-T014 and must keep working with no kwargs — this
    guards against a future edit accidentally making min_pending_age_seconds
    required or changing reconcile_pending_executions()'s positional
    signature."""
    import inspect

    sig = inspect.signature(reconcile_pending_executions)
    params = list(sig.parameters.values())
    assert [p.name for p in params[:3]] == ["execution_store", "journal_db", "open_positions"]
    assert all(p.default is inspect._empty for p in params[:3])
    assert sig.parameters["min_pending_age_seconds"].default == 0.0
