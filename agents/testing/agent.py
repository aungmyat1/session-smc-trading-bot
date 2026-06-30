"""Testing Agent — orchestrates all validation stages in pipeline order."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class Status(str, Enum):
    """Validation outcome."""

    PASS = "PASS"
    FAIL = "FAIL"
    WARNING = "WARNING"
    SKIP = "SKIP"


@dataclass
class StageResult:
    """Result from one validation stage."""

    name: str
    status: Status
    score: float  # 0–100
    coverage: float | None = None
    details: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0


@dataclass
class TestingAgentResult:
    """Consolidated result from all five testing stages."""

    status: Status
    score: float
    coverage: float
    unit_tests: StageResult | None = None
    integration_tests: StageResult | None = None
    strategy_validation: StageResult | None = None
    historical_replay: StageResult | None = None
    regression: StageResult | None = None
    duration_seconds: float = 0.0


class TestingAgent:
    """Runs unit → integration → strategy → replay → regression stages in order.

    Each stage is isolated: a failure in stage N does not prevent N+1 from
    running unless ``fail_fast`` is enabled in config.
    """

    def __init__(self, project_root: Path, config: dict[str, Any]) -> None:
        self._root = project_root
        self._cfg = config
        self._fail_fast: bool = config.get("fail_fast", False)

    def run(self) -> TestingAgentResult:
        """Execute all stages and return a consolidated result."""
        # Import here to allow the agent module to load without all validators installed.
        from agents.testing.validators.unit_validator import UnitValidator
        from agents.testing.validators.integration_validator import IntegrationValidator
        from agents.testing.validators.strategy_validator import StrategyValidator
        from agents.testing.validators.replay_validator import ReplayValidator
        from agents.testing.validators.regression_validator import RegressionValidator

        stages: list[tuple[str, Any]] = [
            ("unit_tests", UnitValidator(self._root, self._cfg)),
            ("integration_tests", IntegrationValidator(self._root, self._cfg)),
            ("strategy_validation", StrategyValidator(self._root, self._cfg)),
            ("historical_replay", ReplayValidator(self._root, self._cfg)),
            ("regression", RegressionValidator(self._root, self._cfg)),
        ]

        logger.info("Testing Agent: %d stages, root=%s", len(stages), self._root)
        t0 = time.monotonic()
        results: dict[str, StageResult] = {}

        for name, validator in stages:
            st = time.monotonic()
            try:
                result: StageResult = validator.validate()
            except Exception as exc:  # noqa: BLE001
                logger.exception("Stage %s raised unexpectedly", name)
                result = StageResult(
                    name=name,
                    status=Status.FAIL,
                    score=0.0,
                    errors=[f"Unhandled: {exc}"],
                )
            result.duration_seconds = time.monotonic() - st
            results[name] = result
            logger.info(
                "  %s → %s (score=%.1f, cov=%s, %.2fs)",
                name,
                result.status.value,
                result.score,
                f"{result.coverage}%" if result.coverage is not None else "—",
                result.duration_seconds,
            )
            if self._fail_fast and result.status == Status.FAIL:
                logger.warning("fail_fast=true — halting after %s", name)
                break

        status, score, cov = self._aggregate(results)
        return TestingAgentResult(
            status=status,
            score=score,
            coverage=cov,
            unit_tests=results.get("unit_tests"),
            integration_tests=results.get("integration_tests"),
            strategy_validation=results.get("strategy_validation"),
            historical_replay=results.get("historical_replay"),
            regression=results.get("regression"),
            duration_seconds=time.monotonic() - t0,
        )

    @staticmethod
    def _aggregate(results: dict[str, StageResult]) -> tuple[Status, float, float]:
        active = [r for r in results.values() if r.status != Status.SKIP]
        score = round(sum(r.score for r in active) / len(active), 1) if active else 0.0
        covs = [r.coverage for r in active if r.coverage is not None]
        cov = round(sum(covs) / len(covs), 1) if covs else 0.0
        any_fail = any(r.status == Status.FAIL for r in active)
        status = Status.FAIL if any_fail else Status.PASS
        return status, score, cov
