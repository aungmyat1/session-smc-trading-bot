"""Quality Agent report — JSON and Markdown output."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agents.quality.agent import QualityAgentResult, StageResult

logger = logging.getLogger(__name__)

_STAGES = ("code_quality", "security", "architecture", "dependency", "documentation")


def _stage_dict(s: StageResult | None) -> dict[str, Any] | None:
    if s is None:
        return None
    return {
        "status": s.status.value,
        "score": s.score,
        "duration_seconds": round(s.duration_seconds, 3),
        "errors": s.errors,
        "warnings": s.warnings,
        "details": s.details,
    }


class QualityReport:
    """Generates JSON and Markdown reports from a QualityAgentResult."""

    def __init__(self, result: QualityAgentResult) -> None:
        self._result = result

    def to_dict(self) -> dict[str, Any]:
        r = self._result
        return {
            "status": r.status.value,
            "quality_score": r.quality_score,
            "security_score": r.security_score,
            "architecture_score": r.architecture_score,
            "documentation_score": r.documentation_score,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "duration_seconds": round(r.duration_seconds, 3),
            "code_quality": _stage_dict(r.code_quality),
            "security": _stage_dict(r.security),
            "architecture": _stage_dict(r.architecture),
            "dependency": _stage_dict(r.dependency),
            "documentation": _stage_dict(r.documentation),
        }

    def write_json(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as fh:
            json.dump(self.to_dict(), fh, indent=2)
        logger.info("Quality report (JSON) → %s", path)

    def write_markdown(self, path: Path) -> None:
        d = self.to_dict()
        icon = "✅" if d["status"] == "PASS" else "❌"
        lines: list[str] = [
            f"# Quality Report {icon}",
            "",
            f"**Status:** `{d['status']}`",
            f"**Quality:** {d['quality_score']}  |  **Security:** {d['security_score']}  |  "
            f"**Architecture:** {d['architecture_score']}  |  **Documentation:** {d['documentation_score']}",
            f"**Generated:** {d['generated_at']}  |  **Duration:** {d['duration_seconds']}s",
            "",
            "## Stage Summary",
            "",
            "| Stage | Status | Score |",
            "|-------|--------|------:|",
        ]
        for key in _STAGES:
            s = d.get(key)
            if s:
                si = "✅" if s["status"] == "PASS" else ("⏭" if s["status"] == "SKIP" else "❌")
                lines.append(f"| {key} | {si} {s['status']} | {s['score']} |")

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
        logger.info("Quality report (MD) → %s", path)
