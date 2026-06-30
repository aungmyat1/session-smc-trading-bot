"""Integration test validator — validates the complete trading pipeline."""

from __future__ import annotations

import logging
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from agents.testing.agent import StageResult, Status

logger = logging.getLogger(__name__)

# Ordered pipeline stages that must all succeed for integration PASS.
PIPELINE_STAGES = [
    "market_data",
    "indicators",
    "session_filter",
    "liquidity_detection",
    "bos",
    "choch",
    "fvg",
    "order_block",
    "risk_engine",
    "execution",
    "database",
]

# Directories to search for integration tests, in priority order.
_CANDIDATE_DIRS = [
    "tests/integration",
    "tests/svos",
    "tests/execution",
    "tests/database",
]


class IntegrationValidator:
    """Runs integration tests and validates the full pipeline stages."""

    def __init__(self, root: Path, config: dict[str, Any]) -> None:
        self._root = root
        self._extra_dirs: list[str] = config.get("integration_test_dirs", [])

    def validate(self) -> StageResult:
        test_dirs = self._resolve_test_dirs()
        if not test_dirs:
            return StageResult(
                name="integration_tests",
                status=Status.SKIP,
                score=100.0,
                details={"reason": "no integration test directories found"},
            )

        report_dir = self._root / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        xml_path = report_dir / "integration-test-results.xml"

        cmd = [
            "python",
            "-m",
            "pytest",
            *[str(d) for d in test_dirs],
            f"--junit-xml={xml_path}",
            "--no-cov",
            "-q",
            "--tb=short",
            "--no-header",
        ]
        logger.debug("Integration cmd: %s", " ".join(cmd))
        proc = subprocess.run(cmd, cwd=self._root, capture_output=True, text=True)
        return self._parse(proc, xml_path)

    def _resolve_test_dirs(self) -> list[Path]:
        found: list[Path] = []
        candidates = list(self._extra_dirs) + _CANDIDATE_DIRS
        for rel in candidates:
            p = self._root / rel
            if p.exists() and any(p.rglob("test_*.py")):
                found.append(p)
        # Deduplicate while preserving order.
        seen: set[Path] = set()
        unique: list[Path] = []
        for p in found:
            if p not in seen:
                seen.add(p)
                unique.append(p)
        return unique

    def _parse(
        self, proc: subprocess.CompletedProcess[str], xml_path: Path
    ) -> StageResult:
        errors: list[str] = []
        warnings: list[str] = []
        details: dict[str, Any] = {"pipeline_stages": PIPELINE_STAGES}

        n_passed = n_failed = n_errors = n_skipped = 0
        stage_coverage: dict[str, bool] = {s: False for s in PIPELINE_STAGES}

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
                    name_lower = tc.get("name", "").lower()
                    cls_lower = tc.get("classname", "").lower()
                    combined = f"{cls_lower} {name_lower}"
                    for stage in PIPELINE_STAGES:
                        if stage.replace("_", "") in combined.replace("_", ""):
                            stage_coverage[stage] = True
                    failure = tc.find("failure")
                    if failure is not None:
                        errors.append(
                            f"FAIL {tc.get('classname', '')}.{tc.get('name', '')}: {failure.get('message', '')[:120]}"
                        )
            except ET.ParseError as exc:
                warnings.append(f"JUnit XML parse error: {exc}")
        elif proc.returncode not in (0, 1, 2):
            errors.append(f"pytest exited {proc.returncode}: {proc.stderr[-400:]}")

        uncovered = [s for s, found in stage_coverage.items() if not found]
        if uncovered:
            warnings.append(
                f"Pipeline stages without dedicated tests: {', '.join(uncovered)}"
            )

        details.update(
            {
                "passed": n_passed,
                "failed": n_failed,
                "errors_count": n_errors,
                "skipped": n_skipped,
                "stage_coverage": stage_coverage,
                "uncovered_stages": uncovered,
            }
        )

        n_total = n_passed + n_failed + n_errors
        pass_rate = (n_passed / n_total * 100.0) if n_total > 0 else 100.0
        coverage_pct = (
            (len(PIPELINE_STAGES) - len(uncovered)) / len(PIPELINE_STAGES)
        ) * 100.0
        score = round(pass_rate * 0.8 + coverage_pct * 0.2, 1)
        failed = n_failed > 0 or n_errors > 0

        return StageResult(
            name="integration_tests",
            status=Status.FAIL if failed else Status.PASS,
            score=score,
            details=details,
            errors=errors,
            warnings=warnings,
        )
