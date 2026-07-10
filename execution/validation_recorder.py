"""
Demo Validation Mode — per-trade, per-stage lifecycle recorder.

Wraps the CanonicalExecutionPipeline event_sink already wired in
scripts/run_st_a2_demo.py (see execution/operations_recorder.py's
OperationsRecorder.event_sink, which this does NOT replace — both sinks run
side by side off the same event) and adds two things neither the pipeline
nor OperationsRecorder currently do:

  1. A validation_session_id tag, so every stage row is attributable to a
     specific Demo Validation Mode campaign (execution/validation_session.py).
  2. A computed duration_ms — the elapsed time since the *previous* recorded
     stage for the same trade_id. No per-stage timing exists anywhere else
     in this codebase (dashboard/status_server.py's _execution_latency() is
     an explicit stub); this is the first real implementation.

Honesty note: CanonicalExecutionPipeline only emits intent_received /
risk_decision / execution_result / intent_rejected / package_rejected today
— it does not see broker acknowledgement, fill, position-open, SL/TP, or
close as distinct pipeline events (those happen inside TradeManager, called
synchronously from the DemoExecutionAdapter). This recorder maps the
pipeline's real events to a smaller, honest set of stages
(signal_generated, risk_evaluation, order_submission, order_rejected) via
`from_pipeline_event`, and exposes `record_stage` directly for the
additional call sites in run_st_a2_demo.py that already detect a close
(_process_closed_positions) or a startup-recovery outcome, so those can be
recorded under their own real stage names (position_close, recovery) without
pretending the pipeline itself saw them.

Design mirrors execution/risk_portfolio_store.py: module-level SessionLocal,
best-effort writes, never raises.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from db.connection import SessionLocal
from db.models import ValidationLifecycleEvent

_log = logging.getLogger("execution.validation_recorder")

# Pipeline event_type -> honest validation stage name. Anything not in this
# map (pipeline_started/pipeline_stopped) is not trade-scoped and is skipped.
_PIPELINE_STAGE_MAP = {
    "intent_received": "signal_generated",
    "risk_decision": "risk_evaluation",
    "execution_result": "order_submission",
    "intent_rejected": "order_rejected",
    "package_rejected": "order_rejected",
}


class ValidationLifecycleRecorder:
    """Records one row per (trade_id, stage) with a computed duration_ms.

    `_last_seen` is an in-memory, best-effort clock reference (monotonic
    seconds) keyed by trade_id — it is instrumentation, not a safety gate,
    so losing it across a process restart is an accepted limitation (a
    restart naturally starts a fresh duration chain for any in-flight
    trade_id, which is still an honest measurement of the post-restart
    stages).
    """

    def __init__(self, validation_session_id: str) -> None:
        self.validation_session_id = validation_session_id
        self._last_seen: dict[str, float] = {}

    def record_stage(
        self,
        trade_id: str,
        stage: str,
        status: str,
        *,
        error: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        now = time.monotonic()
        previous = self._last_seen.get(trade_id)
        duration_ms = round((now - previous) * 1000, 3) if previous is not None else None
        self._last_seen[trade_id] = now

        if SessionLocal is None:
            return
        session = SessionLocal()
        try:
            session.add(ValidationLifecycleEvent(
                validation_session_id=self.validation_session_id,
                trade_id=trade_id,
                stage=stage,
                status=status,
                duration_ms=duration_ms,
                error=error,
                metadata_=metadata or {},
            ))
            session.commit()
        except Exception as exc:
            session.rollback()
            _log.warning("validation lifecycle event skipped (%s/%s): %s", trade_id, stage, exc)
        finally:
            session.close()

    def from_pipeline_event(self, event: Any) -> None:
        """Adapter for CanonicalExecutionPipeline's event_sink — pass this
        bound method alongside (not instead of) OperationsRecorder.event_sink."""
        record = event.to_dict()
        stage = _PIPELINE_STAGE_MAP.get(record.get("event_type", ""))
        if stage is None:
            return
        trade_id = record.get("intent_id") or record.get("event_id", "")
        status = record.get("status", "")
        error = record.get("reason") or None
        self.record_stage(trade_id, stage, status, error=error, metadata={"symbol": record.get("symbol", "")})
