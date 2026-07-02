from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Mapping

REQUIRED_CHECKS = (
    "approved_package",
    "broker_connection",
    "market_data",
    "order_dry_run",
    "risk_firewall",
    "stop_loss_required",
    "max_daily_loss",
    "dashboard",
    "telegram",
    "restart_recovery",
)


@dataclass(frozen=True, slots=True)
class DemoReadinessResult:
    ready: bool
    score: int
    checks: dict[str, bool]
    failed: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def evaluate_demo_readiness(checks: Mapping[str, bool]) -> DemoReadinessResult:
    normalized = {name: checks.get(name) is True for name in REQUIRED_CHECKS}
    failed = tuple(name for name, passed in normalized.items() if not passed)
    score = round(100 * sum(normalized.values()) / len(REQUIRED_CHECKS))
    return DemoReadinessResult(not failed, score, normalized, failed)
