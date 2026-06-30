"""Testing Agent report — JSON and Markdown output."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agents.testing.agent import StageResult, TestingAgentResult

logger = logging.getLogger(__name__)

_STAGES = ("unit_tests", "integration_tests", "strategy_validation", "historical_replay", "regression")


def _stage_dict(s: StageResult | None) -> dict[str, Any] | None:
    if s is None:
        return None
    return {
        "status": s.status.value,
        "score": s.score,
        "coverage": s.coverage,
        "duration_seconds": round(s.duration_seconds, 3),
        "errors": s.errors,
        "warnings": s.warnings,
        "details": s.details,
    }


class TestingReport:
    """Generates JSON and Markdown reports from a TestingAgentResult."""

    def __init__(self, result: TestingAgentResult) -> None:
        self._result = result

    def to_dict(self) -> dict[str, Any]:
        r = self._result
        return {
            "status": r.status.value,
            "score": r.score,
            "coverage": r.coverage,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "duration_seconds": round(r.duration_seconds, 3),
            "unit_tests": _stage_dict(r.unit_tests),
            "integration_tests": _stage_dict(r.integration_tests),
            "strategy_validation": _stage_dict(r.strategy_validation),
            "historical_replay": _stage_dict(r.historical_replay),
            "regression": _stage_dict(r.regression),
        }

    def write_json(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as fh:
            json.dump(self.to_dict(), fh, indent=2)
        logger.info("Testing report (JSON) → %s", path)

    def write_markdown(self, path: Path) -> None:
        d = self.to_dict()
        icon = "✅" if d["status"] == "PASS" else "❌"
        lines: list[str] = [
            f"# Testing Report {icon}",
            "",
            f"**Status:** `{d['status']}`  |  **Score:** {d['score']}  |  **Coverage:** {d['coverage']}%",
            f"**Generated:** {d['generated_at']}  |  **Duration:** {d['duration_seconds']}s",
            "",
            "## Stage Summary",
            "",
            "| Stage | Status | Score | Coverage |",
            "|-------|--------|------:|----------:|",
        ]
        for key in _STAGES:
            s = d.get(key)
            if s:
                cov = f"{s['coverage']}%" if s["coverage"] is not None else "—"
                icon_s = "✅" if s["status"] == "PASS" else ("⏭" if s["status"] == "SKIP" else "❌")
                lines.append(f"| {key} | {icon_s} {s['status']} | {s['score']} | {cov} |")

        for key in _STAGES:
            s = d.get(key)
            if s and (s["errors"] or s["warnings"]):
                lines += ["", f"### {key}"]
                for e in s["errors"]:
                    lines.append(f"- ❌ {e}")
                for w in s["warnings"]:
                    lines.append(f"- ⚠️ {w}")

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + "\n")
        logger.info("Testing report (MD) → %s", path)
