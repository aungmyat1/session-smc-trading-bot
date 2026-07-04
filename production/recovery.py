"""Ordered fail-closed runtime recovery orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Mapping

from production.operations import OperationsRepository


@dataclass(frozen=True, slots=True)
class RecoveryResult:
    ready: bool
    completed_steps: tuple[str, ...]
    blockers: tuple[str, ...]


class RecoveryManager:
    STEPS = ("ownership", "package", "checkpoint", "adapter", "reconcile_account", "reconcile_orders", "reconcile_positions", "ambiguous_submissions")

    def __init__(self, repository: OperationsRepository) -> None:
        self.repository = repository

    async def recover(self, runtime_id: str, handlers: Mapping[str, Callable[[], Any | Awaitable[Any]]]) -> RecoveryResult:
        completed: list[str] = []
        blockers: list[str] = []
        for step in self.STEPS:
            handler = handlers.get(step)
            if handler is None:
                blockers.append(f"missing recovery handler: {step}")
                break
            try:
                value = handler()
                result = await value if hasattr(value, "__await__") else value
            except Exception as exc:
                blockers.append(f"{step}: {exc}")
                break
            if result is False or (isinstance(result, Mapping) and result.get("consistent") is False):
                blockers.append(f"{step}: reconciliation blocked")
                break
            completed.append(step)
            self.repository.checkpoint(runtime_id, {"completed_steps": completed, "blocked": False})
        return RecoveryResult(not blockers and tuple(completed) == self.STEPS, tuple(completed), tuple(blockers))
