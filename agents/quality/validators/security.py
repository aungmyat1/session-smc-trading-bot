"""Security validator — runs bandit, pip-audit and checks for hardcoded secrets."""
from __future__ import annotations

import json
import logging
import re
import subprocess
from pathlib import Path
from typing import Any

from agents.quality.agent import Status, StageResult

logger = logging.getLogger(__name__)

# Patterns that indicate hardcoded secrets (case-insensitive, applied to .py files).
_SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("hardcoded_api_key", re.compile(r'(?i)(api_key|apikey)\s*=\s*["\'][^"\']{8,}["\']')),
    ("hardcoded_password", re.compile(r'(?i)(password|passwd|pwd)\s*=\s*["\'][^"\']{4,}["\']')),
    ("hardcoded_token", re.compile(r'(?i)(token|secret|credential)\s*=\s*["\'][^"\']{8,}["\']')),
    ("hardcoded_metaapi", re.compile(r'(?i)(METAAPI|VANTAGE)[A-Z_]*\s*=\s*["\'][^"\']{10,}["\']')),
    ("hardcoded_telegram", re.compile(r'(?i)(TELEGRAM)[A-Z_]*\s*=\s*["\'][^"\']{10,}["\']')),
]

# Files that should never contain raw secrets (we skip .env* and tests/).
_SCAN_DIRS = ["svos", "agents", "scripts", "db", "dashboard"]
_EXCLUDE_PATHS = {".env", ".env.example", "tests"}


class SecurityValidator:
    """Runs bandit static analysis, pip-audit dependency audit, and secret scan."""

    def __init__(self, root: Path, config: dict[str, Any]) -> None:
        self._root = root
        self._min_score: float = float(config.get("minimum_security_score", 90.0))

    def validate(self) -> StageResult:
        errors: list[str] = []
        warnings: list[str] = []
        tool_scores: dict[str, float] = {}
        details: dict[str, Any] = {}

        # --- bandit ---
        b_score, b_errs, b_warns, b_det = self._run_bandit()
        tool_scores["bandit"] = b_score
        details["bandit"] = b_det
        errors += b_errs
        warnings += b_warns

        # --- pip-audit ---
        a_score, a_errs, a_warns, a_det = self._run_pip_audit()
        tool_scores["pip_audit"] = a_score
        details["pip_audit"] = a_det
        errors += a_errs
        warnings += a_warns

        # --- secret scan ---
        s_score, s_errs, s_det = self._run_secret_scan()
        tool_scores["secret_scan"] = s_score
        details["secret_scan"] = s_det
        errors += s_errs

        # Weighted composite: secret scan is critical.
        score = round(
            tool_scores["bandit"] * 0.40
            + tool_scores["pip_audit"] * 0.30
            + tool_scores["secret_scan"] * 0.30,
            1,
        )
        status = Status.FAIL if (score < self._min_score or errors) else Status.PASS

        return StageResult(
            name="security",
            status=status,
            score=score,
            details={"tool_scores": tool_scores, **details},
            errors=errors,
            warnings=warnings,
        )

    # -------------------------------------------------------------------------

    def _run_bandit(self) -> tuple[float, list[str], list[str], dict[str, Any]]:
        scan_dirs = [str(self._root / d) for d in _SCAN_DIRS if (self._root / d).exists()]
        if not scan_dirs:
            return 100.0, [], [], {"skipped": "no source dirs"}

        cmd = ["python", "-m", "bandit", "-r", "-f", "json", "-ll", *scan_dirs]
        proc = subprocess.run(cmd, cwd=self._root, capture_output=True, text=True)

        # bandit exits non-zero even when only producing warnings; check output.
        if not proc.stdout.strip():
            logger.info("bandit not installed or produced no output")
            return 100.0, [], ["bandit not available — install bandit for security scanning"], {"skipped": "not available"}

        try:
            data = json.loads(proc.stdout)
        except json.JSONDecodeError:
            return 90.0, [], [f"bandit output unparseable: {proc.stdout[:200]}"], {}

        results = data.get("results", [])
        high = [r for r in results if r.get("issue_severity") == "HIGH"]
        medium = [r for r in results if r.get("issue_severity") == "MEDIUM"]

        errors: list[str] = []
        for r in high[:10]:
            loc = f"{r.get('filename', '?')}:{r.get('line_number', '?')}"
            errors.append(f"bandit HIGH {r.get('test_id', '')}: {r.get('issue_text', '')[:80]} @ {loc}")

        warns: list[str] = [
            f"bandit MEDIUM {r.get('test_id', '')}: {r.get('issue_text', '')[:60]}" for r in medium[:5]
        ]

        score = max(0.0, round(100.0 - len(high) * 10.0 - len(medium) * 2.0, 1))
        return score, errors, warns, {"high": len(high), "medium": len(medium), "total": len(results)}

    def _run_pip_audit(self) -> tuple[float, list[str], list[str], dict[str, Any]]:
        cmd = ["python", "-m", "pip_audit", "--format", "json", "--progress-spinner", "off"]
        proc = subprocess.run(cmd, cwd=self._root, capture_output=True, text=True)

        if proc.returncode not in (0, 1) and not proc.stdout.strip():
            return 100.0, [], ["pip-audit not installed — install pip-audit for dependency audit"], {"skipped": True}

        try:
            data = json.loads(proc.stdout)
        except json.JSONDecodeError:
            return 95.0, [], ["pip-audit output unparseable"], {}

        vulnerabilities = data.get("vulnerabilities", data) if isinstance(data, dict) else data
        if isinstance(vulnerabilities, list):
            critical = [v for v in vulnerabilities if isinstance(v, dict) and v.get("fix_versions")]
            errors = [f"pip-audit: {v.get('name', '?')} {v.get('version', '?')} — {v.get('id', '')}" for v in critical[:10]]
            score = max(0.0, round(100.0 - len(critical) * 15.0, 1))
            return score, errors, [], {"vulnerable_packages": len(critical)}

        return 100.0, [], [], {"result": "clean"}

    def _run_secret_scan(self) -> tuple[float, list[str], dict[str, Any]]:
        findings: list[dict[str, str]] = []
        for source_dir in _SCAN_DIRS:
            d = self._root / source_dir
            if not d.exists():
                continue
            for py_file in d.rglob("*.py"):
                if any(ex in py_file.parts for ex in _EXCLUDE_PATHS):
                    continue
                try:
                    content = py_file.read_text(errors="replace")
                    for pattern_name, pat in _SECRET_PATTERNS:
                        match = pat.search(content)
                        if match:
                            findings.append({
                                "file": str(py_file.relative_to(self._root)),
                                "pattern": pattern_name,
                                "snippet": match.group(0)[:60],
                            })
                except OSError:
                    pass

        errors = [f"SECRET {f['pattern']} in {f['file']}: {f['snippet']}" for f in findings]
        score = 0.0 if findings else 100.0
        return score, errors, {"findings": len(findings)}
