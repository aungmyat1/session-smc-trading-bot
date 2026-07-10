"""
Demo Validation Mode — latency/duration metrics.

Pure read-side: queries operations.validation_lifecycle_event
(execution/validation_recorder.py) and computes rolling avg / max / p50 /
p95 / p99 per stage. This is the only place percentiles are computed —
nothing upstream needs to change to support it. Fills the gap identified
during planning: dashboard/status_server.py's `_execution_latency()` is an
explicit stub returning None; no per-stage timing existed anywhere before
execution/validation_recorder.py.

Design mirrors execution/operations_recorder.py's `_read()` helper:
best-effort, defaults to an empty result on any DB failure.
"""

from __future__ import annotations

import logging
from typing import Any

from db.connection import SessionLocal
from db.models import ValidationLifecycleEvent

_log = logging.getLogger("execution.validation_metrics")


def _percentile(sorted_values: list[float], pct: float) -> float:
    """Nearest-rank percentile — no interpolation, matches the simplicity of
    the rest of this codebase's stats (e.g. dashboard/status_server.py's
    existing latency chart uses raw samples, not a stats library)."""
    if not sorted_values:
        return 0.0
    index = min(len(sorted_values) - 1, max(0, round(pct / 100 * (len(sorted_values) - 1))))
    return sorted_values[index]


def stage_latency_stats(validation_session_id: str, stage: str | None = None) -> dict[str, Any]:
    """Per-stage (or all-stage, if *stage* is None) latency summary for one
    validation session: {stage: {count, avg_ms, max_ms, p50_ms, p95_ms, p99_ms}}."""
    if SessionLocal is None:
        return {}
    session = SessionLocal()
    try:
        query = session.query(ValidationLifecycleEvent).filter(
            ValidationLifecycleEvent.validation_session_id == validation_session_id,
            ValidationLifecycleEvent.duration_ms.isnot(None),
        )
        if stage is not None:
            query = query.filter(ValidationLifecycleEvent.stage == stage)
        rows = query.all()
    except Exception as exc:
        _log.warning("validation latency query skipped (%s): %s", validation_session_id, exc)
        return {}
    finally:
        session.close()

    by_stage: dict[str, list[float]] = {}
    for row in rows:
        by_stage.setdefault(row.stage, []).append(row.duration_ms)

    result: dict[str, Any] = {}
    for stage_name, values in by_stage.items():
        values_sorted = sorted(values)
        result[stage_name] = {
            "count": len(values_sorted),
            "avg_ms": round(sum(values_sorted) / len(values_sorted), 3),
            "max_ms": round(max(values_sorted), 3),
            "p50_ms": round(_percentile(values_sorted, 50), 3),
            "p95_ms": round(_percentile(values_sorted, 95), 3),
            "p99_ms": round(_percentile(values_sorted, 99), 3),
        }
    return result


def lifecycle_success_rate(validation_session_id: str) -> dict[str, Any]:
    """Fraction of recorded stages per trade_id that reached a non-error
    status, plus a simple count of distinct trade_ids observed."""
    if SessionLocal is None:
        return {"trade_count": 0, "stage_count": 0, "failed_stage_count": 0, "success_rate": None}
    session = SessionLocal()
    try:
        rows = (
            session.query(ValidationLifecycleEvent)
            .filter(ValidationLifecycleEvent.validation_session_id == validation_session_id)
            .all()
        )
    except Exception as exc:
        _log.warning("validation success-rate query skipped (%s): %s", validation_session_id, exc)
        return {"trade_count": 0, "stage_count": 0, "failed_stage_count": 0, "success_rate": None}
    finally:
        session.close()

    trade_ids = {row.trade_id for row in rows}
    failed = [row for row in rows if row.status in ("REJECTED", "closed_with_error") or row.error]
    total = len(rows)
    return {
        "trade_count": len(trade_ids),
        "stage_count": total,
        "failed_stage_count": len(failed),
        "success_rate": round((total - len(failed)) / total, 4) if total else None,
    }
