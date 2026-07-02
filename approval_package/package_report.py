from __future__ import annotations

from pathlib import Path

from approval_package.package_validator import PackageValidationResult


def write_package_report(result: PackageValidationResult, output: Path | str) -> Path:
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    findings = ["- None"] if not result.reasons else [f"- {reason}" for reason in result.reasons]
    path.write_text("\n".join(["# Approval Package Report", "", f"- Verdict: `{'PASS' if result.valid else 'FAIL'}`", f"- Package: `{result.package_path}`", "", "## Findings", "", *findings]) + "\n", encoding="utf-8")
    return path
