"""Production Approval Agent — consumes Testing and Quality reports, emits APPROVED/REJECTED."""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import yaml

from agents.approval.rules import RuleOutcome, RuleResult, evaluate_rules

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG = "config/approval.yaml"


class ReleaseStatus(str, Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    INCOMPLETE = "INCOMPLETE"  # mandatory upstream reports are missing


@dataclass
class ApprovalResult:
    """Final governance decision with full rule evidence."""

    release_status: ReleaseStatus
    testing_score: float
    quality_score: float
    security_score: float
    architecture_score: float
    strategy_validation_score: float
    historical_validation_status: str
    rule_results: list[RuleResult] = field(default_factory=list)
    failed_mandatory_rules: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0


class ApprovalAgent:
    """Reads Testing and Quality reports, applies governance rules, returns release decision."""

    def __init__(self, project_root: Path, config: dict[str, Any]) -> None:
        self._root = project_root
        self._cfg = config
        self._report_dir = project_root / config.get("report_dir", "reports")

    def run(self) -> ApprovalResult:
        """Load reports, evaluate rules, return approval decision."""
        t0 = time.monotonic()
        reports = self._load_reports()

        missing = [k for k, v in reports.items() if v is None]
        if missing:
            logger.warning("Missing upstream reports: %s", missing)
            return ApprovalResult(
                release_status=ReleaseStatus.INCOMPLETE,
                testing_score=0.0,
                quality_score=0.0,
                security_score=0.0,
                architecture_score=0.0,
                strategy_validation_score=0.0,
                historical_validation_status="MISSING",
                warnings=[f"Missing report: {m}" for m in missing],
                duration_seconds=time.monotonic() - t0,
            )

        safe_reports = {k: v or {} for k, v in reports.items()}
        rule_results = evaluate_rules(safe_reports, self._cfg)

        failed_mandatory = [
            r.rule_id for r in rule_results
            if r.mandatory and r.outcome == RuleOutcome.FAIL
        ]
        warnings = [
            f"{r.rule_id} WARNING: {r.description} ({r.detail})"
            for r in rule_results
            if not r.mandatory and r.outcome == RuleOutcome.FAIL
        ]

        status = ReleaseStatus.APPROVED if not failed_mandatory else ReleaseStatus.REJECTED

        t = safe_reports.get("testing", {})
        q = safe_reports.get("quality", {})

        result = ApprovalResult(
            release_status=status,
            testing_score=float(t.get("score", 0)),
            quality_score=float(q.get("quality_score", 0)),
            security_score=float(q.get("security_score", 0)),
            architecture_score=float(q.get("architecture_score", 0)),
            strategy_validation_score=float((t.get("strategy_validation") or {}).get("score", 0)),
            historical_validation_status=((t.get("historical_replay") or {}).get("status", "SKIP")),
            rule_results=rule_results,
            failed_mandatory_rules=failed_mandatory,
            warnings=warnings,
            duration_seconds=time.monotonic() - t0,
        )

        logger.info(
            "Approval Agent → %s | mandatory_failures=%d testing=%.1f quality=%.1f",
            result.release_status.value,
            len(failed_mandatory),
            result.testing_score,
            result.quality_score,
        )
        return result

    def _load_reports(self) -> dict[str, dict[str, Any] | None]:
        return {
            "testing": self._load_json("testing_report.json"),
            "quality": self._load_json("quality_report.json"),
        }

    def _load_json(self, filename: str) -> dict[str, Any] | None:
        path = self._report_dir / filename
        if not path.exists():
            logger.warning("Report not found: %s", path)
            return None
        try:
            data = json.loads(path.read_text())
            return data if isinstance(data, dict) else None
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("Cannot load %s: %s", path, exc)
            return None


def load_config(root: Path) -> dict[str, Any]:
    """Load approval config; return defaults if file is absent."""
    path = root / _DEFAULT_CONFIG
    if path.exists():
        try:
            return yaml.safe_load(path.read_text()) or {}
        except yaml.YAMLError:
            pass
    return {}
