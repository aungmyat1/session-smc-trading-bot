"""Read-only validation metrics helpers for System 2 dashboard endpoints."""

from __future__ import annotations

from execution.operations_recorder import get_recent_events


def lifecycle_success_rate(session_id: str) -> dict:
    events = [event for event in get_recent_events(limit=500) if event.get("payload", {}).get("session_id") == session_id]
    by_stage: dict[str, dict[str, int | float]] = {}
    for event in events:
        payload = event.get("payload", {})
        stage = str(payload.get("stage", "unknown"))
        status = str(payload.get("status", "")).lower()
        row = by_stage.setdefault(stage, {"total": 0, "success": 0, "success_rate": 0.0})
        row["total"] = int(row["total"]) + 1
        if status in {"success", "pass", "passed", "ok"}:
            row["success"] = int(row["success"]) + 1
    for row in by_stage.values():
        total = int(row["total"])
        row["success_rate"] = (int(row["success"]) / total) if total else 0.0
    return {"session_id": session_id, "stages": by_stage, "event_count": len(events)}


def stage_latency_stats(session_id: str, stage: str | None = None) -> dict:
    events = [event for event in get_recent_events(limit=500) if event.get("payload", {}).get("session_id") == session_id]
    latencies: dict[str, list[float]] = {}
    for event in events:
        payload = event.get("payload", {})
        event_stage = str(payload.get("stage", "unknown"))
        if stage and event_stage != stage:
            continue
        value = payload.get("latency_ms")
        if isinstance(value, int | float):
            latencies.setdefault(event_stage, []).append(float(value))

    stats = {}
    for event_stage, values in latencies.items():
        values = sorted(values)
        count = len(values)
        p50 = values[int((count - 1) * 0.50)] if count else 0.0
        p95 = values[int((count - 1) * 0.95)] if count else 0.0
        p99 = values[int((count - 1) * 0.99)] if count else 0.0
        stats[event_stage] = {
            "count": count,
            "avg_ms": sum(values) / count if count else 0.0,
            "max_ms": max(values) if values else 0.0,
            "p50_ms": p50,
            "p95_ms": p95,
            "p99_ms": p99,
        }
    return {"session_id": session_id, "stage": stage, "stages": stats}
