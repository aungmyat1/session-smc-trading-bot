"""
S2 — State Persistence.

Persists the adaptive engine risk state to data/adaptive_state.json.
Auto-loads on construction; auto-saves on every mutation.

Public API:
    StateStore(path)
        .load()  -> dict
        .save(state)
        .get()   -> dict
        .update(state)
        .reset_daily()
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from adaptive.engine.risk_manager import new_state, reset_daily

_DEFAULT_PATH = Path("data/adaptive_state.json")
_logger = logging.getLogger("adaptive.state_store")


class StateStore:
    def __init__(self, path: Path | str = _DEFAULT_PATH) -> None:
        self._path = Path(path)
        self._state: dict = {}
        self.load()

    # ── I/O ──────────────────────────────────────────────────────────────────

    def load(self) -> dict:
        """Load state from disk. Returns default state if file absent or corrupt."""
        if self._path.exists():
            try:
                data = json.loads(self._path.read_text(encoding="utf-8"))
                base = new_state()
                base.update(data)   # merge: extra keys in file are preserved
                self._state = base
                _logger.info("State loaded from %s", self._path)
                return self._state
            except (json.JSONDecodeError, OSError) as exc:
                _logger.warning("State file unreadable (%s) — starting fresh", exc)
        self._state = new_state()
        return self._state

    def save(self, state: dict | None = None) -> None:
        """Persist state to disk."""
        if state is not None:
            self._state = state
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps(self._state, indent=2, default=str),
                encoding="utf-8",
            )
        except OSError as exc:
            _logger.error("Could not save state: %s", exc)

    # ── Read ─────────────────────────────────────────────────────────────────

    def get(self) -> dict:
        return dict(self._state)

    # ── Mutate + auto-save ───────────────────────────────────────────────────

    def update(self, state: dict) -> None:
        """Replace in-memory state and persist immediately."""
        self._state = state
        self.save()

    def reset_daily(self) -> dict:
        """Reset intra-day counters and persist."""
        self._state = reset_daily(self._state)
        self._state["last_reset"] = datetime.now(timezone.utc).isoformat()
        self.save()
        return self._state

    def needs_daily_reset(self) -> bool:
        """True if last_reset was on a previous UTC date."""
        last = self._state.get("last_reset", "")
        if not last:
            return True
        try:
            last_dt = datetime.fromisoformat(last)
            today = datetime.now(timezone.utc).date()
            return last_dt.date() < today
        except ValueError:
            return True
