"""
System2 Completion Mission — Phase 2: deterministic duplicate-order prevention.

Covers execution.execution_state.build_intent_identity(),
ExecutionStateStore.find_active_by_identity(), and the duplicate-order gate
wired into TradeManager.open_position() (execution/trade_manager.py).

Acceptance criterion under test: 100 duplicate requests for the same signal
must produce exactly 1 broker order.
"""

from __future__ import annotations

import asyncio
import tempfile
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from execution.execution_state import ExecutionStateStore, build_intent_identity
from execution.trade_manager import TradeManager


def _store() -> ExecutionStateStore:
    return ExecutionStateStore(tempfile.mkdtemp())


def _manager(store: ExecutionStateStore | None = None, place_order_delay: float = 0.0):
    executor = MagicMock()

    async def _place_order(**kwargs):
        if place_order_delay:
            await asyncio.sleep(place_order_delay)
        return {"order_id": "BROKER-ORDER-1", "simulated": True}

    executor.place_order = AsyncMock(side_effect=_place_order)
    executor.close_position = AsyncMock(return_value=True)
    executor.modify_position = AsyncMock(return_value=True)
    executor.get_positions = AsyncMock(return_value=[])
    mgr = TradeManager(executor, execution_store=store or _store())
    return mgr, executor


def _signal(*, symbol="EURUSD", side="long", session="london", timestamp="2026-07-12T09:00:00+00:00"):
    return SimpleNamespace(
        pair=symbol, side=side, entry=1.1000, stop_loss=1.0950, take_profit=1.1150,
        strategy_name="ST-A2", session=session, timestamp=timestamp,
    )


class TestBuildIntentIdentity:
    def test_deterministic_same_inputs(self):
        a = build_intent_identity(strategy_id="ST-A2", symbol="EURUSD", direction="buy",
                                   signal_timestamp="2026-07-12T09:00:00+00:00", trading_session="london")
        b = build_intent_identity(strategy_id="ST-A2", symbol="EURUSD", direction="buy",
                                   signal_timestamp="2026-07-12T09:00:00+00:00", trading_session="london")
        assert a == b

    def test_differs_by_symbol(self):
        base = dict(strategy_id="ST-A2", direction="buy",
                    signal_timestamp="2026-07-12T09:00:00+00:00", trading_session="london")
        assert build_intent_identity(symbol="EURUSD", **base) != build_intent_identity(symbol="GBPUSD", **base)

    def test_differs_by_direction(self):
        base = dict(strategy_id="ST-A2", symbol="EURUSD",
                    signal_timestamp="2026-07-12T09:00:00+00:00", trading_session="london")
        assert build_intent_identity(direction="buy", **base) != build_intent_identity(direction="sell", **base)

    def test_differs_by_strategy(self):
        base = dict(symbol="EURUSD", direction="buy",
                    signal_timestamp="2026-07-12T09:00:00+00:00", trading_session="london")
        assert build_intent_identity(strategy_id="ST-A2", **base) != build_intent_identity(strategy_id="LondonBreakout", **base)

    def test_differs_by_session(self):
        base = dict(strategy_id="ST-A2", symbol="EURUSD", direction="buy",
                    signal_timestamp="2026-07-12T09:00:00+00:00")
        assert build_intent_identity(trading_session="london", **base) != build_intent_identity(trading_session="ny", **base)

    def test_differs_across_time_buckets(self):
        base = dict(strategy_id="ST-A2", symbol="EURUSD", direction="buy", trading_session="london")
        a = build_intent_identity(signal_timestamp="2026-07-12T09:00:00+00:00", **base)
        b = build_intent_identity(signal_timestamp="2026-07-12T09:05:00+00:00", **base)
        assert a != b

    def test_same_within_one_time_bucket(self):
        base = dict(strategy_id="ST-A2", symbol="EURUSD", direction="buy", trading_session="london")
        a = build_intent_identity(signal_timestamp="2026-07-12T09:00:00+00:00", **base, time_bucket_seconds=60)
        b = build_intent_identity(signal_timestamp="2026-07-12T09:00:45+00:00", **base, time_bucket_seconds=60)
        assert a == b

    def test_direction_case_and_whitespace_normalized(self):
        base = dict(strategy_id="ST-A2", symbol="EURUSD",
                    signal_timestamp="2026-07-12T09:00:00+00:00", trading_session="london")
        assert build_intent_identity(direction="BUY", **base) == build_intent_identity(direction=" buy ", **base)


class TestFindActiveByIdentity:
    def test_none_when_store_empty(self):
        assert _store().find_active_by_identity("nonexistent") is None

    def test_finds_pending_record(self):
        store = _store()
        record = store.create_record(strategy_id="ST-A2", strategy_version="", signal_id="X")
        found = store.find_active_by_identity("X")
        assert found is not None
        assert found.execution_id == record.execution_id

    def test_ignores_terminal_records(self):
        store = _store()
        record = store.create_record(strategy_id="ST-A2", strategy_version="", signal_id="X")
        store.advance_to_terminal(record.execution_id, "FAILED_TERMINAL")
        assert store.find_active_by_identity("X") is None

    def test_ignores_unrelated_identity(self):
        store = _store()
        store.create_record(strategy_id="ST-A2", strategy_version="", signal_id="X")
        assert store.find_active_by_identity("Y") is None


class TestDuplicateOrderPrevention:
    @pytest.mark.asyncio
    async def test_duplicate_signal_after_broker_acknowledged_is_suppressed(self):
        """The core scenario: same signal submitted twice in sequence (e.g. a
        strategy re-evaluating and re-emitting on consecutive ticks). Second
        call must not reach the broker."""
        mgr, ex = _manager()
        first = await mgr.open_position(_signal(), 0.02)
        assert first.get("duplicate_suppressed") is not True
        assert ex.place_order.await_count == 1

        second = await mgr.open_position(_signal(), 0.02)
        assert second["duplicate_suppressed"] is True
        assert second["duplicate_reason"] == "already_broker_acknowledged"
        assert second["order_id"] == first["order_id"]
        assert ex.place_order.await_count == 1  # still only 1 — no second broker call

    @pytest.mark.asyncio
    async def test_duplicate_while_still_pending_in_flight(self):
        """Simulates a retry/duplicate-dispatch arriving while the original
        submission hasn't reached the broker yet (still SUBMISSION_PENDING —
        the ambiguous/in-flight case). Must not place a second order."""
        store = _store()
        identity = build_intent_identity(
            strategy_id="ST-A2", symbol="EURUSD", direction="buy",
            signal_timestamp="2026-07-12T09:00:00+00:00", trading_session="london",
        )
        record = store.create_record(strategy_id="ST-A2", strategy_version="", signal_id=identity)
        store.transition(record.execution_id, "RISK_APPROVED")
        store.transition(record.execution_id, "SUBMISSION_PENDING")  # no broker_order_id yet

        mgr, ex = _manager(store=store)
        result = await mgr.open_position(_signal(), 0.02)

        assert result["duplicate_suppressed"] is True
        assert result["duplicate_reason"] == "in_flight_ambiguous"
        ex.place_order.assert_not_called()

    @pytest.mark.asyncio
    async def test_duplicate_after_recovery_pending(self):
        """A record left RECOVERY_PENDING by a prior interrupted run (ambiguous
        after a crash/timeout) must also block a fresh duplicate submission
        for the same signal — recovery reconciliation, not open_position(),
        is responsible for resolving it."""
        store = _store()
        identity = build_intent_identity(
            strategy_id="ST-A2", symbol="EURUSD", direction="buy",
            signal_timestamp="2026-07-12T09:00:00+00:00", trading_session="london",
        )
        record = store.create_record(strategy_id="ST-A2", strategy_version="", signal_id=identity)
        store.transition(record.execution_id, "RISK_APPROVED")
        store.transition(record.execution_id, "SUBMISSION_PENDING")
        store.transition(record.execution_id, "RECOVERY_PENDING")

        mgr, ex = _manager(store=store)
        result = await mgr.open_position(_signal(), 0.02)

        assert result["duplicate_suppressed"] is True
        ex.place_order.assert_not_called()

    @pytest.mark.asyncio
    async def test_duplicate_survives_process_restart(self):
        """The store is disk-backed: a brand-new TradeManager instance
        pointed at the same store directory (simulating a process restart)
        must still recognize the earlier BROKER_ACKNOWLEDGED record and
        refuse to place a second order for the same signal."""
        shared_dir = tempfile.mkdtemp()
        store_before_restart = ExecutionStateStore(shared_dir)
        mgr1, ex1 = _manager(store=store_before_restart)
        await mgr1.open_position(_signal(), 0.02)
        assert ex1.place_order.await_count == 1

        # "Restart": a fresh ExecutionStateStore + TradeManager, same path.
        store_after_restart = ExecutionStateStore(shared_dir)
        mgr2, ex2 = _manager(store=store_after_restart)
        result = await mgr2.open_position(_signal(), 0.02)

        assert result["duplicate_suppressed"] is True
        ex2.place_order.assert_not_called()

    @pytest.mark.asyncio
    async def test_duplicate_after_timeout_then_retry(self):
        """A caller that treats a slow/timed-out open_position() call as
        failed and retries must not cause two broker orders if the original
        call actually reaches BROKER_ACKNOWLEDGED before or during the retry."""
        store = _store()
        mgr, ex = _manager(store=store)
        await mgr.open_position(_signal(), 0.02)
        assert ex.place_order.await_count == 1

        # Caller believed the first call timed out / was ambiguous and retries
        # with the identical signal.
        retry = await mgr.open_position(_signal(), 0.02)
        assert retry["duplicate_suppressed"] is True
        assert ex.place_order.await_count == 1

    @pytest.mark.asyncio
    async def test_duplicate_websocket_double_dispatch_concurrent(self):
        """Simulates two near-simultaneous calls for the identical signal
        (e.g. a duplicated websocket/tick event) via asyncio.gather — true
        concurrency within one event loop, not just sequential retries."""
        store = _store()
        mgr, ex = _manager(store=store, place_order_delay=0.01)
        results = await asyncio.gather(
            mgr.open_position(_signal(), 0.02),
            mgr.open_position(_signal(), 0.02),
        )
        assert ex.place_order.await_count == 1
        suppressed = [r for r in results if r.get("duplicate_suppressed")]
        placed = [r for r in results if not r.get("duplicate_suppressed")]
        assert len(placed) == 1
        assert len(suppressed) == 1

    @pytest.mark.asyncio
    async def test_100_duplicate_requests_produce_exactly_one_broker_order(self):
        """The mission's explicit acceptance criterion: 100 duplicate
        requests -> exactly 1 broker order."""
        store = _store()
        mgr, ex = _manager(store=store, place_order_delay=0.001)
        results = await asyncio.gather(*[mgr.open_position(_signal(), 0.02) for _ in range(100)])

        assert ex.place_order.await_count == 1
        placed = [r for r in results if not r.get("duplicate_suppressed")]
        suppressed = [r for r in results if r.get("duplicate_suppressed")]
        assert len(placed) == 1
        assert len(suppressed) == 99

    @pytest.mark.asyncio
    async def test_different_signals_are_not_deduped_false_positive_check(self):
        """Correctness regression guard: genuinely distinct signals (different
        symbol, different direction, different time bucket) must each place
        their own broker order — the dedup gate must never block legitimate,
        non-duplicate trades."""
        store = _store()
        mgr, ex = _manager(store=store)

        await mgr.open_position(_signal(symbol="EURUSD", side="long"), 0.02)
        await mgr.open_position(_signal(symbol="GBPUSD", side="long"), 0.02)
        await mgr.open_position(_signal(symbol="EURUSD", side="short"), 0.02)
        await mgr.open_position(_signal(symbol="EURUSD", side="long", timestamp="2026-07-12T10:00:00+00:00"), 0.02)

        assert ex.place_order.await_count == 4

    @pytest.mark.asyncio
    async def test_duplicate_after_broker_reconnect_same_signal(self):
        """A broker reconnect between two calls for the same signal must not
        reopen the dedup window — the store, not the connection, is the
        source of truth."""
        store = _store()
        mgr, ex = _manager(store=store)
        await mgr.open_position(_signal(), 0.02)

        # Simulate a broker reconnect: replace the executor's place_order
        # mock (as if a new connection object were swapped in) without
        # touching the store.
        ex.place_order = AsyncMock(return_value={"order_id": "BROKER-ORDER-2", "simulated": True})
        result = await mgr.open_position(_signal(), 0.02)

        assert result["duplicate_suppressed"] is True
        ex.place_order.assert_not_called()
