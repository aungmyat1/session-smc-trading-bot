#!/usr/bin/env python3
"""Check that the broker/auth section in CLAUDE.md matches deployed demo config."""

from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

import yaml


def _extract_pairs_from_runner(path: Path) -> list[str]:
    module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in module.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "PAIRS":
                    value = ast.literal_eval(node.value)
                    if isinstance(value, list):
                        return [str(item) for item in value]
    raise ValueError(f"Could not locate PAIRS list in {path}")


def _extract_claude_section(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    match = re.search(r"## §5 — BROKER / AUTH(.*?)(?:\n## |\Z)", text, re.S)
    if not match:
        raise ValueError(f"Could not locate §5 broker/auth section in {path}")
    return match.group(1)


def _extract_claude_magic(section: str) -> int:
    match = re.search(r"Magic number[s]?:\s*(?:flat\s+)?`?(\d+)`?", section, re.I)
    if not match:
        raise ValueError("Could not find magic number declaration in CLAUDE.md §5")
    return int(match.group(1))


def _extract_claude_pairs(section: str) -> list[str]:
    match = re.search(r"Live-traded pairs:\s*([A-Z0-9,\s]+)", section)
    if not match:
        raise ValueError("Could not find live-traded pairs declaration in CLAUDE.md §5")
    return [part.strip() for part in match.group(1).split(",") if part.strip()]


def check_repo(repo_root: Path) -> list[str]:
    claude_path = repo_root / "CLAUDE.md"
    config_path = repo_root / "config" / "demo.yaml"
    runner_path = repo_root / "scripts" / "run_st_a2_demo.py"

    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    configured_magic = int(config["execution"]["magic_number"])
    configured_pairs = [str(item) for item in config["trading"]["allowed_pairs"]]
    runner_pairs = _extract_pairs_from_runner(runner_path)

    section = _extract_claude_section(claude_path)
    claude_magic = _extract_claude_magic(section)
    claude_pairs = _extract_claude_pairs(section)

    issues: list[str] = []
    if claude_magic != configured_magic:
        issues.append(
            f"CLAUDE.md §5 magic number mismatch: docs={claude_magic} config/demo.yaml={configured_magic}"
        )
    if claude_pairs != runner_pairs:
        issues.append(
            f"CLAUDE.md §5 live-traded pairs mismatch: docs={claude_pairs} scripts/run_st_a2_demo.py={runner_pairs}"
        )
    missing_from_config = [pair for pair in runner_pairs if pair not in configured_pairs]
    if missing_from_config:
        issues.append(
            "Runner trades pairs missing from config/demo.yaml allowed_pairs: "
            + ", ".join(missing_from_config)
        )
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Repository root")
    args = parser.parse_args()

    repo_root = Path(args.root).resolve()
    issues = check_repo(repo_root)
    if issues:
        print("[docs-drift — FAIL]")
        for issue in issues:
            print(f"  - {issue}")
        return 1
    print("[docs-drift — PASS] CLAUDE.md §5 matches config/demo.yaml and scripts/run_st_a2_demo.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
