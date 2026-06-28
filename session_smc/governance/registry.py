"""
Strategy registry — JSON-backed persistent store for strategy lifecycle state.

Registry file: data/strategy_registry.json
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .lifecycle import LifecycleState, StrategyLifecycle, LifecycleTransitionError

logger = logging.getLogger(__name__)

_UTC = timezone.utc
DEFAULT_REGISTRY_PATH = Path("data/strategy_registry.json")


class StrategyRegistryError(Exception):
    """Raised for registry-level errors (duplicate ID, missing strategy, etc.)."""


class StrategyRegistry:
    """
    JSON-backed registry for strategy lifecycle state.

    All mutations auto-persist to disk.

    Usage::
        reg = StrategyRegistry()
        reg.register("ST-A2", initial_state=LifecycleState.RESEARCH_QUALIFIED,
                     meta={"pairs": ["EURUSD", "GBPUSD"]})
        reg.promote("ST-A2", LifecycleState.VERIFICATION_READY,
                    evidence={"evidence_type": "backtest_report",
                               "description": "ST-A2 PF_2x=1.025 PASS",
                               "timestamp": "2026-06-21T10:04:58Z"})
        state = reg.get_state("ST-A2")
    """

    def __init__(self, registry_path: Path = DEFAULT_REGISTRY_PATH) -> None:
        self._path = Path(registry_path)
        self._strategies: dict[str, StrategyLifecycle] = {}
        self._meta: dict[str, dict] = {}
        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register(
        self,
        strategy_id: str,
        initial_state: LifecycleState = LifecycleState.RESEARCH_QUALIFIED,
        meta: Optional[dict] = None,
        overwrite: bool = False,
    ) -> StrategyLifecycle:
        """Register a new strategy. Raises if already exists unless overwrite=True."""
        if strategy_id in self._strategies and not overwrite:
            raise StrategyRegistryError(
                f"Strategy '{strategy_id}' already registered. "
                "Use overwrite=True to replace."
            )
        lc = StrategyLifecycle(strategy_id=strategy_id, state=initial_state)
        self._strategies[strategy_id] = lc
        self._meta[strategy_id] = {
            **(meta or {}),
            "registered_at": datetime.now(_UTC).isoformat(),
        }
        self._persist()
        logger.info("Registered strategy '%s' in state '%s'", strategy_id, initial_state.value)
        return lc

    def promote(
        self,
        strategy_id: str,
        new_state: LifecycleState,
        evidence: dict,
        actor: str = "system",
    ) -> None:
        """Promote strategy to a new lifecycle state."""
        lc = self._get(strategy_id)
        lc.transition(new_state, evidence=evidence, actor=actor)
        self._persist()

    def suspend(
        self,
        strategy_id: str,
        reason: str,
        actor: str = "system",
    ) -> None:
        """Suspend a strategy (halt trading)."""
        self.promote(
            strategy_id,
            LifecycleState.SUSPENDED,
            evidence={
                "evidence_type": "suspension_reason",
                "description": reason,
                "timestamp": datetime.now(_UTC).isoformat(),
            },
            actor=actor,
        )

    def rollback(
        self,
        strategy_id: str,
        reason: str,
        actor: str = "system",
    ) -> None:
        """Roll back a strategy (emergency revert)."""
        self.promote(
            strategy_id,
            LifecycleState.ROLLBACK,
            evidence={
                "evidence_type": "rollback_reason",
                "description": reason,
                "timestamp": datetime.now(_UTC).isoformat(),
            },
            actor=actor,
        )

    def get_state(self, strategy_id: str) -> LifecycleState:
        return self._get(strategy_id).state

    def get_lifecycle(self, strategy_id: str) -> StrategyLifecycle:
        return self._get(strategy_id)

    def get_meta(self, strategy_id: str) -> dict:
        if strategy_id not in self._meta:
            raise StrategyRegistryError(f"Strategy '{strategy_id}' not found.")
        return self._meta[strategy_id]

    def list_strategies(self) -> list[str]:
        return list(self._strategies.keys())

    def snapshot(self) -> dict:
        """Return full registry snapshot as a serialisable dict."""
        return {
            sid: {
                "state": lc.state.value,
                "meta": self._meta.get(sid, {}),
                "history_len": len(lc.history),
                "created_at": lc.created_at,
            }
            for sid, lc in self._strategies.items()
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get(self, strategy_id: str) -> StrategyLifecycle:
        if strategy_id not in self._strategies:
            raise StrategyRegistryError(f"Strategy '{strategy_id}' not found.")
        return self._strategies[strategy_id]

    def _persist(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "updated_at": datetime.now(_UTC).isoformat(),
            "strategies": {
                sid: lc.to_dict()
                for sid, lc in self._strategies.items()
            },
            "meta": self._meta,
        }
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2))
        tmp.replace(self._path)
        logger.debug("Registry persisted to %s", self._path)

    def _load(self) -> None:
        if not self._path.exists():
            logger.debug("No registry file at %s — starting fresh.", self._path)
            return
        try:
            raw = json.loads(self._path.read_text())
            for sid, lc_dict in raw.get("strategies", {}).items():
                self._strategies[sid] = StrategyLifecycle.from_dict(lc_dict)
            self._meta = raw.get("meta", {})
            logger.info("Loaded %d strategies from registry.", len(self._strategies))
        except Exception as exc:
            logger.error("Failed to load registry from %s: %s", self._path, exc)
