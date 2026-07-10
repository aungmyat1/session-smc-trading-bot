"""
Durable Postgres-backed risk/portfolio state store.

SYSTEM2_MASTER_PLAN.md Phase 2 — replaces the JSON-file persistence added in
Phase 1 (`logs/risk_state.json`, `logs/portfolio_state.json`) with transactional
Postgres storage using the `operations.risk_portfolio_state` table (migration 005).

Design principles (identical to execution/operations_recorder.py):
  - Best-effort: DB failures are logged and swallowed, never crash the tick loop.
  - The existing JSON files remain as a read-only fallback source.
  - Every significant event (trade_close, daily_reset, startup_restore) also
    appends a row to the operations.risk_portfolio_history audit trail.
  - Tick-interval saves upsert the current-state row only (no history row —
    too noisy at 60s intervals).

Public API:
    store = RiskPortfolioStore()
    store.save_risk_state(data, runtime_id, event="tick_save")
    store.save_portfolio_state(data, runtime_id, event="tick_save")
    store.load_risk_state() -> dict | None
    store.load_portfolio_state() -> dict | None
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any

from db.connection import SessionLocal
from db.models import RiskPortfolioHistory, RiskPortfolioState

_log = logging.getLogger("execution.risk_portfolio_store")

# Events that deserve a history row (audit trail) in addition to the
# current-state upsert.  Tick saves are too frequent for history.
_HISTORY_EVENTS = frozenset({"trade_close", "daily_reset", "startup_restore", "halt_engaged"})


class RiskPortfolioStore:
    """Durable Postgres-backed risk/portfolio state.

    Replaces ``logs/risk_state.json`` and ``logs/portfolio_state.json`` as the
    authoritative state source.  Falls back to None on read when the DB is
    unavailable — the caller is responsible for trying JSON next.
    """

    # ── Writes ────────────────────────────────────────────────────────────

    def save_risk_state(
        self,
        data: dict[str, Any],
        runtime_id: str,
        event: str = "tick_save",
    ) -> None:
        """Upsert today's risk state.  If *event* is significant, also
        append a history row."""
        self._upsert("risk", data, runtime_id, event)

    def save_portfolio_state(
        self,
        data: dict[str, Any],
        runtime_id: str,
        event: str = "tick_save",
    ) -> None:
        """Upsert today's portfolio state.  If *event* is significant, also
        append a history row."""
        self._upsert("portfolio", data, runtime_id, event)

    # ── Reads ─────────────────────────────────────────────────────────────

    def load_risk_state(self) -> dict[str, Any] | None:
        """Return the most recent risk state, or ``None`` if unavailable."""
        return self._load_latest("risk")

    def load_portfolio_state(self) -> dict[str, Any] | None:
        """Return the most recent portfolio state, or ``None`` if unavailable."""
        return self._load_latest("portfolio")

    # ── Internals ─────────────────────────────────────────────────────────

    def _upsert(
        self,
        state_type: str,
        data: dict[str, Any],
        runtime_id: str,
        event: str,
    ) -> None:
        if SessionLocal is None:
            return
        session = SessionLocal()
        try:
            today = date.today()
            now = datetime.now(timezone.utc)

            # Atomic upsert: INSERT … ON CONFLICT … DO UPDATE
            existing = (
                session.query(RiskPortfolioState)
                .filter_by(state_type=state_type, period_date=today)
                .first()
            )
            if existing is None:
                session.add(RiskPortfolioState(
                    runtime_id=runtime_id,
                    state_type=state_type,
                    state_data=data,
                    period_date=today,
                    updated_at=now,
                ))
            else:
                existing.state_data = data
                existing.runtime_id = runtime_id
                existing.updated_at = now

            # Append history row for significant events only.
            if event in _HISTORY_EVENTS:
                session.add(RiskPortfolioHistory(
                    runtime_id=runtime_id,
                    state_type=state_type,
                    event=event,
                    state_data=data,
                ))

            session.commit()
        except Exception as exc:
            session.rollback()
            _log.warning("risk_portfolio_store write skipped (%s/%s): %s", state_type, event, exc)
        finally:
            session.close()

    def _load_latest(self, state_type: str) -> dict[str, Any] | None:
        if SessionLocal is None:
            return None
        session = SessionLocal()
        try:
            row = (
                session.query(RiskPortfolioState)
                .filter_by(state_type=state_type)
                .order_by(RiskPortfolioState.period_date.desc())
                .first()
            )
            if row is not None:
                return dict(row.state_data)
            return None
        except Exception as exc:
            _log.warning("risk_portfolio_store read skipped (%s): %s", state_type, exc)
            return None
        finally:
            session.close()
