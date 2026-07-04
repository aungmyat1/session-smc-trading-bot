"""
Startup recovery — resolves incomplete ExecutionRecords left behind by an
interrupted run before the runner processes any new market data.

Wires the previously-dead `ExecutionStateStore.recover_incomplete()` (ROADMAP.md
Phase 1, WS5) to the already-declared ambiguity policy
(`RetryPolicy.ambiguity_policy == "reconcile_before_retry"` in
execution/trade_manager.py): an interrupted order submission is resolved by
checking whether the broker actually holds a matching position, never by
retrying or resubmitting. This is what guarantees idempotent recovery — no
code path here ever calls `place_order`/`open_position`.

Resolution rules, per incomplete ExecutionRecord:
  - `broker_order_id` already known (crash happened after broker
    acknowledgement, before journaling completed): ensure a journal row
    exists for it, then advance the record to COMPLETED.
  - No `broker_order_id` yet (crash happened before or during submission):
    look for a currently-open broker position matching the record's
    symbol/direction/lots that isn't already linked to any journaled trade.
      - Match found -> the order DID reach the broker; adopt its id,
        backfill the journal, advance to COMPLETED.
      - No match -> no evidence the order ever reached the broker; advance
        to FAILED_TERMINAL. The signal is lost, not resubmitted.

Also flags broker positions that carry no execution/journal linkage at all
(`orphaned_positions`) for operator attention — these are never mutated.

Public API:
    reconcile_pending_executions(execution_store, journal_db, open_positions) -> ReconciliationReport
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from core.trade_journal_db import TradeJournalDB
from execution.execution_state import ExecutionRecord, ExecutionStateStore
from shared.strategy_api import Signal

_log = logging.getLogger("execution.startup_recovery")


@dataclass(slots=True)
class ResolvedExecution:
    execution_id: str
    final_state: str
    broker_order_id: str
    note: str


@dataclass(slots=True)
class ReconciliationReport:
    resolved: list[ResolvedExecution] = field(default_factory=list)
    orphaned_positions: list[dict[str, Any]] = field(default_factory=list)

    @property
    def recovered_count(self) -> int:
        return sum(1 for r in self.resolved if r.final_state == "COMPLETED")

    @property
    def lost_count(self) -> int:
        return sum(1 for r in self.resolved if r.final_state == "FAILED_TERMINAL")


def reconcile_pending_executions(
    execution_store: ExecutionStateStore,
    journal_db: TradeJournalDB,
    open_positions: list[dict[str, Any]],
) -> ReconciliationReport:
    incomplete = execution_store.recover_incomplete()
    linked_order_ids = journal_db.get_broker_order_ids()
    position_by_id = {str(p["id"]): p for p in open_positions if p.get("id")}

    resolved: list[ResolvedExecution] = []
    for record in incomplete:
        outcome = _reconcile_one(record, execution_store, journal_db, position_by_id, linked_order_ids)
        resolved.append(outcome)
        if outcome.broker_order_id:
            linked_order_ids.add(outcome.broker_order_id)

    claimed_ids = {r.broker_order_id for r in resolved if r.broker_order_id}
    orphaned = [
        pos for pid, pos in position_by_id.items()
        if pid not in linked_order_ids and pid not in claimed_ids
    ]
    return ReconciliationReport(resolved=resolved, orphaned_positions=orphaned)


def _reconcile_one(
    record: ExecutionRecord,
    execution_store: ExecutionStateStore,
    journal_db: TradeJournalDB,
    position_by_id: dict[str, dict[str, Any]],
    linked_order_ids: set[str],
) -> ResolvedExecution:
    meta = record.state_history[0].get("metadata", {}) if record.state_history else {}

    if record.broker_order_id:
        if record.broker_order_id not in linked_order_ids:
            _backfill_journal(journal_db, record, meta, position_by_id.get(record.broker_order_id))
        execution_store.advance_to_terminal(
            record.execution_id, "COMPLETED",
            metadata={"reconciliation": "resumed_after_restart"},
        )
        return ResolvedExecution(
            record.execution_id, "COMPLETED", record.broker_order_id,
            "broker_order_id already known from prior run; journal ensured",
        )

    match = _find_unlinked_match(position_by_id, linked_order_ids, meta)
    if match is not None:
        order_id = str(match["id"])
        _backfill_journal(journal_db, record, meta, match, order_id_override=order_id)
        # No-op state transition (target == current) purely to attach the
        # discovered broker_order_id/position_ref before advancing.
        execution_store.transition(
            record.execution_id, record.state,
            broker_order_id=order_id, position_ref=order_id,
        )
        execution_store.advance_to_terminal(
            record.execution_id, "COMPLETED",
            metadata={"reconciliation": "matched_unlinked_open_position"},
        )
        return ResolvedExecution(
            record.execution_id, "COMPLETED", order_id,
            "no broker_order_id recorded, but a matching unlinked open position was found — recovered",
        )

    _log.warning(
        "Startup recovery: execution %s (%s) has no broker_order_id and no matching "
        "open position — treating as lost, NOT resubmitting.",
        record.execution_id, meta.get("symbol", ""),
    )
    execution_store.advance_to_terminal(
        record.execution_id, "FAILED_TERMINAL",
        metadata={"reconciliation": "no_matching_broker_position_found"},
    )
    return ResolvedExecution(
        record.execution_id, "FAILED_TERMINAL", "",
        "no broker evidence the order was ever submitted; signal lost, not resubmitted",
    )


def _find_unlinked_match(
    position_by_id: dict[str, dict[str, Any]],
    linked_order_ids: set[str],
    meta: dict[str, Any],
) -> dict[str, Any] | None:
    symbol = str(meta.get("symbol") or "")
    direction = str(meta.get("direction") or "").lower()
    lots = meta.get("lots")
    for pid, pos in position_by_id.items():
        if pid in linked_order_ids:
            continue
        if symbol and str(pos.get("symbol") or "") != symbol:
            continue
        if direction and str(pos.get("direction") or "").lower() != direction:
            continue
        if lots is not None and pos.get("lots") is not None:
            try:
                if abs(float(pos["lots"]) - float(lots)) > 1e-6:
                    continue
            except (TypeError, ValueError):
                pass
        return pos
    return None


def _backfill_journal(
    journal_db: TradeJournalDB,
    record: ExecutionRecord,
    meta: dict[str, Any],
    position: dict[str, Any] | None,
    order_id_override: str | None = None,
) -> int:
    """Insert a best-effort journal row for a position/order discovered only
    via startup reconciliation, so later close-detection can find it. Marked
    `reconciled=True` in metadata since fields unknown at signal time (SL/TP,
    risk_percent) fall back to Signal's defaults rather than being fabricated."""
    order_id = order_id_override or record.broker_order_id
    direction = str(meta.get("direction") or "").lower()
    action = "BUY" if direction == "buy" else "SELL" if direction == "sell" else direction.upper()
    entry_price = float(position.get("entry") or 0.0) if position else 0.0

    signal = Signal(
        timestamp=datetime.now(timezone.utc),
        strategy_name=record.strategy_id or "unknown",
        symbol=str(meta.get("symbol") or ""),
        action=action or "BUY",
        entry_price=entry_price,
        metadata={
            "reconciled": True,
            "reconciliation_source": "startup_recovery",
            "execution_id": record.execution_id,
        },
    )
    return journal_db.record_signal(
        signal,
        router_result="RECONCILED",
        execution_result="OPEN",
        broker_order_id=order_id,
        position_size=float(meta.get("lots") or 0.0),
    )
