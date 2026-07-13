#!/usr/bin/env python3
"""Flag new governance-doc strategy claims for pre-merge evidence review."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


CLAIM_RE = re.compile(
    r"\b(PASS|FAIL|FAILED|BLOCKED|APPROVED|DEPLOYED|FROZEN|"
    r"paper-enabled|demo-enabled|live-enabled)\b",
    re.IGNORECASE,
)
GOVERNANCE_PATHS = (
    "SYSTEM2_MASTER_PLAN.md",
    "docs/00_Project/",
    "docs/operations/",
    "docs/VERDICT_LOG.md",
)


def run_git(args: list[str]) -> str:
    completed = subprocess.run(
        ["git", *args],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return completed.stdout


def is_governance_path(path: str) -> bool:
    return path == "SYSTEM2_MASTER_PLAN.md" or any(
        path.startswith(prefix) for prefix in GOVERNANCE_PATHS[1:]
    )


def changed_governance_files(base_ref: str) -> list[str]:
    output = run_git(["diff", "--name-only", base_ref, "--", *GOVERNANCE_PATHS])
    return [line for line in output.splitlines() if line and is_governance_path(line)]


def added_claim_lines(base_ref: str, path: str) -> list[str]:
    diff = run_git(["diff", "--unified=0", base_ref, "--", path])
    claims: list[str] = []
    for line in diff.splitlines():
        if not line.startswith("+") or line.startswith("+++"):
            continue
        text = line[1:]
        if CLAIM_RE.search(text):
            claims.append(text)
    return claims


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "List new PASS/FAIL/BLOCKED/approval/deployment claims in "
            "governance-facing docs so they can be checked against "
            "VERDICT_LOG.md, docs/audit, reports, and the base branch."
        )
    )
    parser.add_argument(
        "--base",
        default="origin/develop",
        help="Base ref to diff against, default: origin/develop",
    )
    args = parser.parse_args()

    repo_root = Path(run_git(["rev-parse", "--show-toplevel"]).strip())
    print(f"Repository: {repo_root}")
    print(f"Base ref: {args.base}")

    files = changed_governance_files(args.base)
    findings: list[tuple[str, list[str]]] = []
    for path in files:
        claims = added_claim_lines(args.base, path)
        if claims:
            findings.append((path, claims))

    if not findings:
        print("No new governance-doc strategy/status claims found.")
        return 0

    print("New governance-doc claims require evidence review before merge:")
    for path, claims in findings:
        print(f"\n{path}")
        for claim in claims:
            print(f"  + {claim}")

    print(
        "\nVerify each claim against docs/VERDICT_LOG.md, docs/audit/, "
        "reports/, and the pre-merge base branch. BLOCKED is not FAIL."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
