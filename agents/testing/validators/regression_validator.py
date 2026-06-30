"""Regression validator — detects unexpected changes in test results vs baseline."""

from __future__ import annotations

import json
import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from agents.testing.agent import Status, StageResult

logger = logging.getLogger(__name__)

_BASELINE_PATH = "reports/testing_baseline.json"


class RegressionValidator:
    """Compares current pytest results against a stored baseline.

    If no baseline exists, the current run is saved as the new baseline and the
    stage returns PASS — establishing the regression anchor for future runs.

    Fails if any metric regresses beyond its configured tolerance.
    """

    def __init__(self, root: Path, config: dict[str, Any]) -> None:
        self._root = root
        self._baseline_path = root / config.get("baseline_path", _BASELINE_PATH)
        self._tolerances: dict[str, float] = {
            "pass_rate": float(config.get("regression_tolerance_pass_rate", 5.0)),
            "coverage": float(config.get("regression_tolerance_coverage", 3.0)),
            "duration": float(config.get("regression_tolerance_duration_pct", 50.0)),
        }

    def validate(self) -> StageResult:
        current = self._collect_current()
        if not self._baseline_path.exists():
            self._save_baseline(current)
            return StageResult(
                name="regression",
                status=Status.PASS,
                score=100.0,
                details={"action": "baseline_created", "metrics": current},
                warnings=["No baseline found — created new baseline from current run"],
            )

        baseline = self._load_baseline()
        if baseline is None:
            return StageResult(
                name="regression",
                status=Status.WARNING,
                score=90.0,
                details={"action": "baseline_unreadable"},
                warnings=[
                    "Baseline file exists but could not be parsed — skipping regression check"
                ],
            )

        regressions, improvements = self._compare(current, baseline)
        score = max(0.0, round(100.0 - len(regressions) * 20.0, 1))

        details: dict[str, Any] = {
            "current": current,
            "baseline": baseline,
            "regressions": regressions,
            "improvements": improvements,
        }
        errors = [
            f"REGRESSION {k}: {v['current']} vs baseline {v['baseline']} (delta={v['delta']:.2f})"
            for k, v in regressions.items()
        ]
        info_warnings = [
            f"IMPROVED {k}: {v['current']} vs baseline {v['baseline']}"
            for k, v in improvements.items()
        ]

        # Update baseline if no regressions.
        if not regressions:
            self._save_baseline(current)

        return StageResult(
            name="regression",
            status=Status.FAIL if regressions else Status.PASS,
            score=score,
            details=details,
            errors=errors,
            warnings=info_warnings,
        )

    # -------------------------------------------------------------------------

    def _collect_current(self) -> dict[str, float]:
        xml_path = self._root / "reports" / "unit-test-results.xml"
        cov_json = self._root / "reports" / "unit-coverage.json"

        pass_rate = self._parse_pass_rate(xml_path)
        coverage = self._parse_coverage(cov_json)
        return {"pass_rate": pass_rate, "coverage": coverage}

    @staticmethod
    def _parse_pass_rate(xml_path: Path) -> float:
        if not xml_path.exists():
            return -1.0
        try:
            root_el = ET.parse(xml_path).getroot()
            suite = (
                root_el
                if root_el.tag == "testsuite"
                else (root_el.find("testsuite") or root_el)
            )
            total = int(suite.get("tests", 0))
            failures = int(suite.get("failures", 0)) + int(suite.get("errors", 0))
            return round((total - failures) / total * 100.0, 2) if total > 0 else -1.0
        except (ET.ParseError, ZeroDivisionError):
            return -1.0

    @staticmethod
    def _parse_coverage(cov_json: Path) -> float:
        if not cov_json.exists():
            return -1.0
        try:
            data = json.loads(cov_json.read_text())
            return round(float(data.get("totals", {}).get("percent_covered", -1.0)), 2)
        except (json.JSONDecodeError, KeyError, TypeError):
            return -1.0

    def _compare(
        self,
        current: dict[str, float],
        baseline: dict[str, float],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        regressions: dict[str, Any] = {}
        improvements: dict[str, Any] = {}
        for metric, tolerance in self._tolerances.items():
            if metric == "duration":
                continue  # Duration tolerance checked separately if tracked
            cur = current.get(metric, -1.0)
            base = baseline.get(metric, -1.0)
            if cur < 0 or base < 0:
                continue
            delta = base - cur  # positive = current is worse
            if delta > tolerance:
                regressions[metric] = {
                    "current": cur,
                    "baseline": base,
                    "delta": delta,
                    "tolerance": tolerance,
                }
            elif cur - base > 0:
                improvements[metric] = {"current": cur, "baseline": base}
        return regressions, improvements

    def _load_baseline(self) -> dict[str, float] | None:
        try:
            return json.loads(self._baseline_path.read_text())
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Cannot load baseline %s: %s", self._baseline_path, exc)
            return None

    def _save_baseline(self, data: dict[str, float]) -> None:
        self._baseline_path.parent.mkdir(parents=True, exist_ok=True)
        self._baseline_path.write_text(json.dumps(data, indent=2))
        logger.info("Regression baseline saved → %s", self._baseline_path)
