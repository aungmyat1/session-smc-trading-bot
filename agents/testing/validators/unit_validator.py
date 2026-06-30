"""Unit test validator — runs pytest with coverage and parses JUnit XML output."""

from __future__ import annotations

import json
import logging
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from agents.testing.agent import StageResult, Status

logger = logging.getLogger(__name__)


class UnitValidator:
    """Executes pytest against unit test directories and collects coverage metrics."""

    _CANDIDATE_DIRS = ["tests/unit", "tests"]

    def __init__(self, root: Path, config: dict[str, Any]) -> None:
        self._root = root
        self._min_coverage: float = float(config.get("minimum_coverage", 67.0))
        self._extra_dirs: list[str] = config.get("unit_test_dirs", [])

    def validate(self) -> StageResult:
        test_dir = self._resolve_test_dir()
        if test_dir is None:
            return StageResult(
                name="unit_tests",
                status=Status.SKIP,
                score=100.0,
                details={"reason": "no unit test directories found"},
            )

        report_dir = self._root / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        xml_path = report_dir / "unit-test-results.xml"
        cov_json = report_dir / "unit-coverage.json"

        cmd = [
            "python",
            "-m",
            "pytest",
            str(test_dir),
            f"--junit-xml={xml_path}",
            "--cov=svos",
            f"--cov-report=json:{cov_json}",
            "--cov-report=term-missing:skip-covered",
            "-q",
            "--tb=short",
            "--no-header",
        ]
        logger.debug("Unit test command: %s", " ".join(cmd))
        proc = subprocess.run(cmd, cwd=self._root, capture_output=True, text=True)
        return self._parse(proc, xml_path, cov_json)

    def _resolve_test_dir(self) -> Path | None:
        candidates = list(self._extra_dirs) + self._CANDIDATE_DIRS
        for rel in candidates:
            p = self._root / rel
            if p.exists() and any(p.rglob("test_*.py")):
                logger.debug("Unit test dir resolved to %s", p)
                return p
        return None

    def _parse(
        self,
        proc: subprocess.CompletedProcess[str],
        xml_path: Path,
        cov_json: Path,
    ) -> StageResult:
        errors: list[str] = []
        warnings: list[str] = []
        details: dict[str, Any] = {}

        # --- parse JUnit XML --------------------------------------------------
        n_passed = n_failed = n_errors = n_skipped = 0
        if xml_path.exists():
            try:
                root_el = ET.parse(xml_path).getroot()
                suite = (
                    root_el
                    if root_el.tag == "testsuite"
                    else (root_el.find("testsuite") or root_el)
                )
                total = int(suite.get("tests", 0))
                n_failed = int(suite.get("failures", 0))
                n_errors = int(suite.get("errors", 0))
                n_skipped = int(suite.get("skipped", 0))
                n_passed = max(0, total - n_failed - n_errors - n_skipped)
                for tc in suite.iter("testcase"):
                    failure = tc.find("failure")
                    if failure is not None:
                        msg = failure.get("message", "")[:120]
                        errors.append(
                            f"FAIL {tc.get('classname', '')}.{tc.get('name', '')}: {msg}"
                        )
            except ET.ParseError as exc:
                warnings.append(f"JUnit XML parse error: {exc}")
        else:
            # Fallback: scan stdout for summary line
            for line in proc.stdout.splitlines():
                stripped = line.strip()
                if "passed" in stripped or "failed" in stripped or "error" in stripped:
                    details["pytest_summary"] = stripped
                    break
            if proc.returncode not in (0, 1, 2):
                errors.append(f"pytest exited {proc.returncode}: {proc.stderr[-400:]}")

        details["passed"] = n_passed
        details["failed"] = n_failed
        details["errors_count"] = n_errors
        details["skipped"] = n_skipped

        # --- parse coverage JSON ----------------------------------------------
        coverage: float | None = None
        if cov_json.exists():
            try:
                raw = json.loads(cov_json.read_text())
                coverage = round(
                    float(raw.get("totals", {}).get("percent_covered", 0.0)), 1
                )
                details["coverage_pct"] = coverage
                if coverage < self._min_coverage:
                    errors.append(
                        f"Coverage {coverage}% below required {self._min_coverage}%"
                    )
            except (json.JSONDecodeError, KeyError, TypeError) as exc:
                warnings.append(f"Coverage JSON parse error: {exc}")

        n_total = n_passed + n_failed + n_errors
        pass_rate = (n_passed / n_total * 100.0) if n_total > 0 else 100.0
        cov_contrib = coverage or 0.0
        score = round(pass_rate * 0.7 + cov_contrib * 0.3, 1)

        failed = (n_failed > 0 or n_errors > 0) or (
            coverage is not None and coverage < self._min_coverage
        )
        return StageResult(
            name="unit_tests",
            status=Status.FAIL if failed else Status.PASS,
            score=score,
            coverage=coverage,
            details=details,
            errors=errors,
            warnings=warnings,
        )
