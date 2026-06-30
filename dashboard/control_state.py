from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTROL_STATE_PATH = ROOT / "reports" / "control_state.json"

DEFAULT_CONTROL_STATE = {
    "emergency_stop": {
        "active": False,
        "reason": "",
        "activated_at": "",
        "activated_by": "dashboard",
        "cleared_at": "",
        "cleared_by": "",
        "clear_reason": "",
    },
    "reports_reviewed": {},
    "incidents_reviewed": {},
}


def _merge_default(payload: dict[str, Any]) -> dict[str, Any]:
    merged = {
        "emergency_stop": dict(DEFAULT_CONTROL_STATE["emergency_stop"]),
        "reports_reviewed": dict(DEFAULT_CONTROL_STATE["reports_reviewed"]),
        "incidents_reviewed": dict(DEFAULT_CONTROL_STATE["incidents_reviewed"]),
    }
    merged["emergency_stop"].update(payload.get("emergency_stop", {}))
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
    CONTROL_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONTROL_STATE_PATH.write_text(
        json.dumps(state, indent=2, sort_keys=True), encoding="utf-8"
    )
    return state


def activate_emergency_stop(
    *, reason: str, activated_by: str = "dashboard"
) -> dict[str, Any]:
    state = load_control_state()
    state["emergency_stop"] = {
        "active": True,
        "reason": reason,
        "activated_at": datetime.now(timezone.utc).isoformat(),
        "activated_by": activated_by,
        "cleared_at": "",
        "cleared_by": "",
        "clear_reason": "",
    }
    return save_control_state(state)


def clear_emergency_stop(
    *, reason: str, cleared_by: str = "dashboard"
) -> dict[str, Any]:
    state = load_control_state()
    current = state.get("emergency_stop", {})
    state["emergency_stop"] = {
        "active": False,
        "reason": current.get("reason", ""),
        "activated_at": current.get("activated_at", ""),
        "activated_by": current.get("activated_by", "dashboard"),
        "cleared_at": datetime.now(timezone.utc).isoformat(),
        "cleared_by": cleared_by,
        "clear_reason": reason,
    }
    return save_control_state(state)


def mark_report_reviewed(report_id: str) -> dict[str, Any]:
    state = load_control_state()
    state["reports_reviewed"][report_id] = datetime.now(timezone.utc).isoformat()
    return save_control_state(state)


def mark_incident_reviewed(incident_id: str) -> dict[str, Any]:
    state = load_control_state()
    state["incidents_reviewed"][incident_id] = datetime.now(timezone.utc).isoformat()
    return save_control_state(state)
