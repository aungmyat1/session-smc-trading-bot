"""
Storage governance cleanup report — dry-run only, read-only.

Classifies candidate paths from config/storage_policy.yaml's cache_cleanup
section into safe / requires-confirmation / never-clean tiers, reports their
current size, and estimates reclaimable space. Never deletes, moves, or
modifies anything — this is the reporting half of storage governance; actual
cleanup remains a separate, explicitly-approved, manually-run action (see
docs/operations/storage-governance.md).

Usage:
    python3 scripts/cleanup_report.py
    python3 scripts/cleanup_report.py --json
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import yaml

_ROOT = Path(__file__).resolve().parent.parent
_POLICY_PATH = _ROOT / "config" / "storage_policy.yaml"


def _load_policy() -> dict:
    return yaml.safe_load(_POLICY_PATH.read_text(encoding="utf-8"))


def _du_bytes(path: Path) -> int | None:
    if not path.exists():
        return None
    try:
        out = subprocess.run(
            ["du", "-sb", str(path)], capture_output=True, text=True, timeout=30
        )
        if out.returncode != 0:
            return None
        return int(out.stdout.split()[0])
    except (subprocess.SubprocessError, ValueError, IndexError):
        return None


def _fmt_bytes(n: int | None) -> str:
    if n is None:
        return "unknown"
    for unit in ("B", "K", "M", "G", "T"):
        if abs(n) < 1024:
            return f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}P"


def _classify(paths: list[str], tier: str) -> list[dict]:
    rows = []
    for p in paths:
        expanded = Path(os.path.expanduser(p))
        b = _du_bytes(expanded)
        rows.append({
            "policy_path": p,
            "resolved_path": str(expanded),
            "exists": expanded.exists(),
            "bytes": b,
            "human": _fmt_bytes(b),
            "tier": tier,
        })
    return rows


def build_report() -> dict:
    policy = _load_policy()
    cc = policy["cache_cleanup"]
    safe = _classify(cc.get("safe_paths", []), "safe")
    confirm = _classify(cc.get("requires_confirmation_paths", []), "requires_confirmation")
    never = _classify(cc.get("never_clean_paths", []), "never_clean")
    reclaimable = sum(r["bytes"] or 0 for r in safe)
    return {
        "safe": safe,
        "requires_confirmation": confirm,
        "never_clean": never,
        "reclaimable_bytes": reclaimable,
        "reclaimable_human": _fmt_bytes(reclaimable),
    }


def _print_human(report: dict) -> None:
    print("SAFE — regenerable, no dependency on live state (report only, not auto-cleaned):")
    for r in report["safe"]:
        flag = "" if r["exists"] else "  (not present)"
        print(f"  {r['human']:>8}  {r['resolved_path']}{flag}")
    print(f"\n  Total reclaimable if cleaned: {report['reclaimable_human']}")

    print("\nREQUIRES CONFIRMATION — regenerable in principle, tied to active tool state:")
    for r in report["requires_confirmation"]:
        flag = "" if r["exists"] else "  (not present)"
        print(f"  {r['human']:>8}  {r['resolved_path']}{flag}")

    print("\nNEVER CLEAN — trading data, broker/MT5 state, databases, backups, the repo itself:")
    for r in report["never_clean"]:
        flag = "" if r["exists"] else "  (not present)"
        print(f"  {r['human']:>8}  {r['resolved_path']}{flag}")

    print("\nNo files were modified or deleted by this script.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()
    report = build_report()
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        _print_human(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
