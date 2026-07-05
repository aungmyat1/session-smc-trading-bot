from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONTROL_STATE_PATH = ROOT / "reports" / "control_state.json"

DEFAULT_CONTROL_STATE = {
    "operating_mode": "NORMAL",
    "emergency_stop": {
        "active": False,
        "reason": "",
        "scope": "block_only",
        "source": "",
        "activated_at": "",
        "activated_by": "dashboard",
        "cleared_at": "",
        "cleared_by": "",
        "clear_reason": "",
    },
    "health": {
        "safe_mode": {
            "active": False,
            "reason": "",
            "activated_at": "",
            "activated_by": "",
        },
        "critical_unknown": False,
    },
    "reconciliation": {
        "status": "in_sync",
        "severity": "info",
        "summary": "",
        "detected_at": "",
        "block_new_trading": False,
    },
    "maintenance": {
        "active": False,
        "reason": "",
        "scheduled_at": "",
        "scheduled_by": "",
    },
    "trading_permission": {
        "trading_allowed": True,
        "mode": "NORMAL",
        "close_only": False,
        "reasons": [],
        "source_versions": {},
        "updated_at": "",
    },
    "control_events": [],
    "reports_reviewed": {},
    "incidents_reviewed": {},
    "updated_at": "",
}


def _merge_default(payload: dict[str, Any]) -> dict[str, Any]:
    merged = {
        "operating_mode": payload.get("operating_mode", DEFAULT_CONTROL_STATE["operating_mode"]),
        "emergency_stop": dict(DEFAULT_CONTROL_STATE["emergency_stop"]),
        "health": {
            "safe_mode": dict(DEFAULT_CONTROL_STATE["health"]["safe_mode"]),
            "critical_unknown": bool(
                payload.get("health", {}).get(
                    "critical_unknown",
                    DEFAULT_CONTROL_STATE["health"]["critical_unknown"],
                )
            ),
        },
        "reconciliation": dict(DEFAULT_CONTROL_STATE["reconciliation"]),
        "maintenance": dict(DEFAULT_CONTROL_STATE["maintenance"]),
        "trading_permission": dict(DEFAULT_CONTROL_STATE["trading_permission"]),
        "control_events": list(payload.get("control_events", DEFAULT_CONTROL_STATE["control_events"])),
        "reports_reviewed": dict(DEFAULT_CONTROL_STATE["reports_reviewed"]),
        "incidents_reviewed": dict(DEFAULT_CONTROL_STATE["incidents_reviewed"]),
        "updated_at": str(payload.get("updated_at", DEFAULT_CONTROL_STATE["updated_at"])),
    }
    merged["emergency_stop"].update(payload.get("emergency_stop", {}))
    merged["health"]["safe_mode"].update(payload.get("health", {}).get("safe_mode", {}))
    merged["reconciliation"].update(payload.get("reconciliation", {}))
    merged["maintenance"].update(payload.get("maintenance", {}))
    merged["trading_permission"].update(payload.get("trading_permission", {}))
    merged["reports_reviewed"].update(payload.get("reports_reviewed", {}))
    merged["incidents_reviewed"].update(payload.get("incidents_reviewed", {}))
    return merged


def load_control_state() -> dict[str, Any]:
    if not CONTROL_STATE_PATH.exists():
        return _merge_default({})
    try:
        payload = json.loads(CONTROL_STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return _merge_default({})
    return _merge_default(payload if isinstance(payload, dict) else {})


def save_control_state(payload: dict[str, Any]) -> dict[str, Any]:
    state = _merge_default(payload)
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    CONTROL_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONTROL_STATE_PATH.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
    return state


def _record_control_event(state: dict[str, Any], *, action: str, actor: str, detail: dict[str, Any]) -> dict[str, Any]:
    events = list(state.get("control_events", []))
    events.append(
        {
            "action": action,
            "actor": actor,
            "detail": detail,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    state["control_events"] = events[-200:]
    return state


def activate_emergency_stop(
    *,
    reason: str,
    activated_by: str = "dashboard",
    scope: str = "block_only",
    source: str = "",
) -> dict[str, Any]:
    """`source` identifies which control path created this stop (e.g.
    "control_pause", "control_close_all", "strategy_toggle:<id>",
    "emergency_stop_endpoint") so a scoped resume path (see
    clear_emergency_stop's expected_source) can refuse to clear a stop it
    didn't create. Empty string = unscoped/legacy caller."""
    state = load_control_state()
    state["operating_mode"] = "EMERGENCY_STOP"
    state["emergency_stop"] = {
        "active": True,
        "reason": reason,
        "scope": scope,
        "source": source,
        "activated_at": datetime.now(timezone.utc).isoformat(),
        "activated_by": activated_by,
        "cleared_at": "",
        "cleared_by": "",
        "clear_reason": "",
    }
    _record_control_event(
        state,
        action="emergency_stop_activated",
        actor=activated_by,
        detail={"reason": reason, "scope": scope, "source": source},
    )
    return save_control_state(state)


def clear_emergency_stop(
    *, reason: str, cleared_by: str = "dashboard", expected_source: str | None = None
) -> dict[str, Any]:
    """If `expected_source` is given and an emergency stop is active whose
    `source` doesn't match, refuse — return the state unchanged (still
    active) rather than clearing a stop this caller didn't create. Callers
    that must remain able to clear any active stop (e.g. the global
    resume/clear endpoints) simply omit expected_source."""
    state = load_control_state()
    current = state.get("emergency_stop", {})
    if expected_source is not None and current.get("active") and current.get("source", "") != expected_source:
        return state
    state["operating_mode"] = "NORMAL"
    state["emergency_stop"] = {
        "active": False,
        "reason": current.get("reason", ""),
        "scope": current.get("scope", "block_only"),
        "source": current.get("source", ""),
        "activated_at": current.get("activated_at", ""),
        "activated_by": current.get("activated_by", "dashboard"),
        "cleared_at": datetime.now(timezone.utc).isoformat(),
        "cleared_by": cleared_by,
        "clear_reason": reason,
    }
    _record_control_event(
        state,
        action="emergency_stop_cleared",
        actor=cleared_by,
        detail={"reason": reason},
    )
    return save_control_state(state)


def set_safe_mode(
    *,
    reason: str,
    activated_by: str = "system",
    critical_unknown: bool = False,
) -> dict[str, Any]:
    state = load_control_state()
    state["operating_mode"] = "SAFE_MODE"
    state["health"]["safe_mode"] = {
        "active": True,
        "reason": reason,
        "activated_at": datetime.now(timezone.utc).isoformat(),
        "activated_by": activated_by,
    }
    state["health"]["critical_unknown"] = critical_unknown
    _record_control_event(
        state,
        action="safe_mode_activated",
        actor=activated_by,
        detail={"reason": reason, "critical_unknown": critical_unknown},
    )
    return save_control_state(state)


def clear_safe_mode(*, cleared_by: str = "system") -> dict[str, Any]:
    state = load_control_state()
    state["operating_mode"] = "NORMAL"
    state["health"]["safe_mode"] = dict(DEFAULT_CONTROL_STATE["health"]["safe_mode"])
    state["health"]["critical_unknown"] = False
    _record_control_event(
        state,
        action="safe_mode_cleared",
        actor=cleared_by,
        detail={},
    )
    return save_control_state(state)


def set_reconciliation_status(
    *,
    status: str,
    severity: str,
    summary: str,
    block_new_trading: bool,
) -> dict[str, Any]:
    state = load_control_state()
    state["reconciliation"] = {
        "status": status,
        "severity": severity,
        "summary": summary,
        "detected_at": datetime.now(timezone.utc).isoformat(),
        "block_new_trading": block_new_trading,
    }
    if block_new_trading and state.get("operating_mode") == "NORMAL":
        state["operating_mode"] = "BLOCK_NEW"
    _record_control_event(
        state,
        action="reconciliation_updated",
        actor="reconcile_positions",
        detail=state["reconciliation"],
    )
    return save_control_state(state)


def set_trading_permission(snapshot: dict[str, Any]) -> dict[str, Any]:
    state = load_control_state()
    state["trading_permission"] = snapshot
    return save_control_state(state)


def mark_report_reviewed(report_id: str) -> dict[str, Any]:
    state = load_control_state()
    state["reports_reviewed"][report_id] = datetime.now(timezone.utc).isoformat()
    return save_control_state(state)


def mark_incident_reviewed(incident_id: str) -> dict[str, Any]:
    state = load_control_state()
    state["incidents_reviewed"][incident_id] = datetime.now(timezone.utc).isoformat()
    return save_control_state(state)
