"""Approval Agent report — JSON and Markdown production readiness output."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agents.approval.agent import ApprovalResult, ReleaseStatus

logger = logging.getLogger(__name__)


class ApprovalReport:
    """Generates production readiness reports from an ApprovalResult."""

    def __init__(self, result: ApprovalResult) -> None:
        self._r = result

    def to_dict(self) -> dict[str, Any]:
        r = self._r
        return {
            "release_status": r.release_status.value,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "duration_seconds": round(r.duration_seconds, 3),
            "testing_score": r.testing_score,
            "quality_score": r.quality_score,
            "security_score": r.security_score,
            "architecture_score": r.architecture_score,
            "strategy_validation": r.strategy_validation_score,
            "historical_validation": r.historical_validation_status,
            "mandatory_failures": r.failed_mandatory_rules,
            "warnings": r.warnings,
            "rules": [
                {
                    "id": rr.rule_id,
                    "description": rr.description,
                    "outcome": rr.outcome.value,
                    "mandatory": rr.mandatory,
                    "actual": rr.actual,
                    "threshold": rr.threshold,
                    "detail": rr.detail,
                }
                for rr in r.rule_results
            ],
        }

    def write_json(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as fh:
            json.dump(self.to_dict(), fh, indent=2)
        logger.info("Approval report (JSON) → %s", path)

    def write_markdown(self, path: Path) -> None:
        r = self._r
        d = self.to_dict()
        icon = (
            "✅ APPROVED"
            if r.release_status == ReleaseStatus.APPROVED
            else "❌ REJECTED"
        )
        if r.release_status.value == "INCOMPLETE":
            icon = "⚠️ INCOMPLETE"

        lines: list[str] = [
            f"# Production Readiness Report — {icon}",
            "",
            f"**Decision:** `{r.release_status.value}`  |  **Generated:** {d['generated_at']}",
            "",
            "## Score Summary",
            "",
            "| Dimension | Score |",
            "|-----------|------:|",
            f"| Testing | {r.testing_score} |",
            f"| Quality | {r.quality_score} |",
            f"| Security | {r.security_score} |",
            f"| Architecture | {r.architecture_score} |",
            f"| Strategy Validation | {r.strategy_validation_score} |",
            f"| Historical Validation | {r.historical_validation_status} |",
            "",
            "## Governance Rules",
            "",
            "| Rule | Description | Mandatory | Result |",
            "|------|-------------|:---------:|:------:|",
        ]

        for rr in r.rule_results:
            o_icon = {"PASS": "✅", "FAIL": "❌", "SKIP": "⏭"}.get(
                rr.outcome.value, "?"
            )
            m_icon = "🔒" if rr.mandatory else "—"
            lines.append(
                f"| `{rr.rule_id}` | {rr.description} | {m_icon} | {o_icon} {rr.outcome.value} |"
            )

        if r.failed_mandatory_rules:
            lines += ["", "## Failed Mandatory Rules", ""]
            for rule_id in r.failed_mandatory_rules:
                rule = next(
                    (rr for rr in r.rule_results if rr.rule_id == rule_id), None
                )
                detail = rule.detail if rule else ""
                lines.append(f"- **{rule_id}**: {detail}")

        if r.warnings:
            lines += ["", "## Warnings (non-blocking)", ""]
            for w in r.warnings:
                lines.append(f"- ⚠️ {w}")

        if r.release_status == ReleaseStatus.APPROVED:
            lines += [
                "",
                "---",
                "",
                "> ✅ All mandatory governance gates passed. Release is approved for promotion.",
            ]
        else:
            lines += [
                "",
                "---",
                "",
                "> ❌ Mandatory governance gates failed. Release is BLOCKED. Fix all ❌ mandatory rules before re-approval.",
            ]

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + "\n")
        logger.info("Approval report (MD) → %s", path)
