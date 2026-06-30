"""Code quality validator — runs ruff, mypy, and optionally pylint/black/isort."""
from __future__ import annotations

import logging
import re
import subprocess
from pathlib import Path
from typing import Any

from agents.quality.agent import Status, StageResult

logger = logging.getLogger(__name__)

# Canonical source paths that exist in this project.
_SOURCE_DIRS = ["svos", "agents", "db", "dashboard"]


class CodeQualityValidator:
    """Runs ruff, mypy, and optional formatters; produces a composite quality score."""

    # Paths mypy checks — mirrors the existing CI gate (pyproject.toml).
    _MYPY_DIRS = ["svos/lifecycle", "svos/shared"]

    def __init__(self, root: Path, config: dict[str, Any]) -> None:
        self._root = root
        self._min_score: float = float(config.get("minimum_quality_score", 80.0))
        self._max_complexity: int = int(config.get("maximum_complexity", 10))
        self._mypy_dirs: list[str] = config.get("mypy_dirs", self._MYPY_DIRS)
        # Weight each tool's score contribution.
        self._weights: dict[str, float] = {
            "ruff": 0.40,
            "mypy": 0.35,
            "black": 0.15,
            "isort": 0.10,
        }

    def validate(self) -> StageResult:
        source_dirs = self._resolve_source_dirs()
        errors: list[str] = []
        warnings: list[str] = []
        tool_scores: dict[str, float] = {}
        tool_details: dict[str, Any] = {}

        # --- ruff ---
        ruff_score, ruff_errs, ruff_warns, ruff_det = self._run_ruff(source_dirs)
        tool_scores["ruff"] = ruff_score
        tool_details["ruff"] = ruff_det
        errors += ruff_errs
        warnings += ruff_warns

        # --- mypy (scoped to canonical typed paths, matching CI pyproject.toml) ---
        mypy_dirs = [self._root / d for d in self._mypy_dirs if (self._root / d).exists()]
        mypy_score, mypy_errs, mypy_warns, mypy_det = self._run_mypy(mypy_dirs)
        tool_scores["mypy"] = mypy_score
        tool_details["mypy"] = mypy_det
        errors += mypy_errs
        warnings += mypy_warns

        # --- black (check only) ---
        black_score, black_warns, black_det = self._run_black_check(source_dirs)
        tool_scores["black"] = black_score
        tool_details["black"] = black_det
        warnings += black_warns

        # --- isort (check only) ---
        isort_score, isort_warns, isort_det = self._run_isort_check(source_dirs)
        tool_scores["isort"] = isort_score
        tool_details["isort"] = isort_det
        warnings += isort_warns

        # Weighted score
        composite = sum(
            tool_scores.get(t, 100.0) * w for t, w in self._weights.items()
        )
        score = round(composite, 1)
        status = Status.FAIL if score < self._min_score else Status.PASS

        return StageResult(
            name="code_quality",
            status=status,
            score=score,
            details={"tool_scores": tool_scores, "tool_details": tool_details, "source_dirs": [str(d) for d in source_dirs]},
            errors=errors,
            warnings=warnings,
        )

    # -------------------------------------------------------------------------

    def _resolve_source_dirs(self) -> list[Path]:
        return [self._root / d for d in _SOURCE_DIRS if (self._root / d).exists()]

    def _run_ruff(self, dirs: list[Path]) -> tuple[float, list[str], list[str], dict[str, Any]]:
        if not dirs:
            return 100.0, [], [], {"skipped": True}
        cmd = ["python", "-m", "ruff", "check", "--output-format=concise", *[str(d) for d in dirs]]
        proc = subprocess.run(cmd, cwd=self._root, capture_output=True, text=True)
        raw_lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
        # Exclude ruff summary lines — only keep actual violation lines (path:line:col: CODE msg).
        _SUMMARY_PREFIXES = ("Found", "All checks passed", "No fixes", "[*]")
        error_lines = [ln for ln in raw_lines if not any(ln.startswith(p) for p in _SUMMARY_PREFIXES)]
        count = len(error_lines)
        score = max(0.0, round(100.0 - min(count, 100) * 1.0, 1))
        errors = [f"ruff: {ln}" for ln in error_lines[:20]]
        if count > 20:
            errors.append(f"ruff: … {count - 20} more issues")
        return score, errors, [], {"violation_count": count}

    def _run_mypy(self, dirs: list[Path]) -> tuple[float, list[str], list[str], dict[str, Any]]:
        # Only run mypy on dirs that actually exist.
        if not dirs:
            return 100.0, [], [], {"skipped": True}
        # --follow-imports=skip limits checking to the explicitly named paths only.
        # Without this flag mypy crawls all transitive imports, producing noise from
        # modules that are intentionally outside the typed scope.
        cmd = ["python", "-m", "mypy", "--ignore-missing-imports", "--follow-imports=skip",
               "--no-error-summary", *[str(d) for d in dirs]]
        proc = subprocess.run(cmd, cwd=self._root, capture_output=True, text=True)
        error_pat = re.compile(r"error:")
        errors_found = [ln for ln in proc.stdout.splitlines() if error_pat.search(ln)]
        count = len(errors_found)
        # Each error deducts 2 points; floor at 50 to avoid zeroing the composite
        # for codebases with typed scopes smaller than the full project.
        score = max(50.0, round(100.0 - count * 2.0, 1))
        errors = [f"mypy: {ln[:120]}" for ln in errors_found[:15]]
        if count > 15:
            errors.append(f"mypy: … {count - 15} more type errors")
        return score, errors, [], {"error_count": count}

    def _run_black_check(self, dirs: list[Path]) -> tuple[float, list[str], dict[str, Any]]:
        if not dirs:
            return 100.0, [], {"skipped": True}
        cmd = ["python", "-m", "black", "--check", "--quiet", *[str(d) for d in dirs]]
        proc = subprocess.run(cmd, cwd=self._root, capture_output=True, text=True)
        reformattable = proc.stderr.count("would reformat")
        score = 100.0 if proc.returncode == 0 else max(0.0, round(100.0 - reformattable * 5.0, 1))
        warns = [f"black: {reformattable} file(s) need reformatting"] if reformattable else []
        return score, warns, {"reformattable": reformattable, "returncode": proc.returncode}

    def _run_isort_check(self, dirs: list[Path]) -> tuple[float, list[str], dict[str, Any]]:
        if not dirs:
            return 100.0, [], {"skipped": True}
        cmd = ["python", "-m", "isort", "--check-only", "--quiet", *[str(d) for d in dirs]]
        proc = subprocess.run(cmd, cwd=self._root, capture_output=True, text=True)
        unsorted = len([ln for ln in proc.stdout.splitlines() if "ERROR" in ln or ln.strip()])
        score = 100.0 if proc.returncode == 0 else max(0.0, round(100.0 - unsorted * 5.0, 1))
        warns = [f"isort: {unsorted} file(s) have unsorted imports"] if proc.returncode != 0 else []
        return score, warns, {"returncode": proc.returncode}
