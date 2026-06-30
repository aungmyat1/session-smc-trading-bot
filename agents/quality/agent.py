"""Quality Agent — orchestrates code quality, security and architecture gates."""

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
    """Result from one quality validation stage."""

    name: str
    status: Status
    score: float  # 0–100
    details: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0


@dataclass
class QualityAgentResult:
    """Consolidated result from all quality stages."""

    status: Status
    quality_score: float
    security_score: float
    architecture_score: float
    documentation_score: float
    code_quality: StageResult | None = None
    security: StageResult | None = None
    architecture: StageResult | None = None
    dependency: StageResult | None = None
    documentation: StageResult | None = None
    duration_seconds: float = 0.0


class QualityAgent:
    """Runs code-quality → security → architecture → dependency → documentation in order."""

    def __init__(self, project_root: Path, config: dict[str, Any]) -> None:
        self._root = project_root
        self._cfg = config
        self._fail_fast: bool = config.get("fail_fast", False)

    def run(self) -> QualityAgentResult:
        """Execute all quality stages and return a consolidated result."""
        from agents.quality.validators.code_quality import CodeQualityValidator
        from agents.quality.validators.security import SecurityValidator
        from agents.quality.validators.architecture import ArchitectureValidator
        from agents.quality.validators.dependency import DependencyValidator
        from agents.quality.validators.documentation import DocumentationValidator

        stages: list[tuple[str, Any]] = [
            ("code_quality", CodeQualityValidator(self._root, self._cfg)),
            ("security", SecurityValidator(self._root, self._cfg)),
            ("architecture", ArchitectureValidator(self._root, self._cfg)),
            ("dependency", DependencyValidator(self._root, self._cfg)),
            ("documentation", DocumentationValidator(self._root, self._cfg)),
        ]

        logger.info("Quality Agent: %d stages, root=%s", len(stages), self._root)
        t0 = time.monotonic()
        results: dict[str, StageResult] = {}

        for name, validator in stages:
            st = time.monotonic()
            try:
                result: StageResult = validator.validate()
            except Exception as exc:  # noqa: BLE001
                logger.exception("Quality stage %s raised unexpectedly", name)
                result = StageResult(
                    name=name,
                    status=Status.FAIL,
                    score=0.0,
                    errors=[f"Unhandled: {exc}"],
                )
            result.duration_seconds = time.monotonic() - st
            results[name] = result
            logger.info(
                "  %s → %s (%.1f, %.2fs)",
                name,
                result.status.value,
                result.score,
                result.duration_seconds,
            )
            if self._fail_fast and result.status == Status.FAIL:
                logger.warning("fail_fast=true — halting after %s", name)
                break

        def _score(key: str) -> float:
            r = results.get(key)
            return r.score if r and r.status != Status.SKIP else 100.0

        active = [r for r in results.values() if r.status != Status.SKIP]
        any_fail = any(r.status == Status.FAIL for r in active)
        status = Status.FAIL if any_fail else Status.PASS

        return QualityAgentResult(
            status=status,
            quality_score=_score("code_quality"),
            security_score=_score("security"),
            architecture_score=_score("architecture"),
            documentation_score=_score("documentation"),
            code_quality=results.get("code_quality"),
            security=results.get("security"),
            architecture=results.get("architecture"),
            dependency=results.get("dependency"),
            documentation=results.get("documentation"),
            duration_seconds=time.monotonic() - t0,
        )
