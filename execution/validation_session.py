"""Lightweight validation-session state for System 2 dashboard endpoints."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


class ValidationSessionManager:
    def __init__(self, state_path: Path | None = None) -> None:
        self.state_path = state_path or Path("logs") / "validation_session.json"

    def _default(self) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        return {
            "session_id": f"validation-{uuid4().hex[:8]}",
            "status": "idle",
            "started_at": now,
            "updated_at": now,
            "stages": [],
        }

    def _read(self) -> dict:
        if not self.state_path.exists():
            return self._default()
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
            return payload if isinstance(payload, dict) else self._default()
        except Exception:
            return self._default()

    def active_session(self) -> dict:
        return self._read()

    def resume(self, session_id: str) -> dict:
        payload = self._read()
        if str(payload.get("session_id", "")) == str(session_id):
            return payload
        payload["requested_session_id"] = session_id
        payload["status"] = "not_found"
        return payload
