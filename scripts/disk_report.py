"""
Storage governance disk report — read-only.

Reports total/free disk, the largest directories/files under $HOME, log
growth signals, PostgreSQL data-directory size, ~/archives size, MT5/Wine
footprint, and cache footprint — all against the thresholds in
config/storage_policy.yaml.

Performs NO cleanup and NO deletion. See docs/operations/storage-governance.md.

Usage:
    python3 scripts/disk_report.py
    python3 scripts/disk_report.py --json
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

_ROOT = Path(__file__).resolve().parent.parent
_HOME = Path.home()
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


def _disk_usage() -> dict:
    total, used, free = shutil.disk_usage("/")
    return {
        "total": total,
        "used": used,
        "free": free,
        "used_pct": round(used / total * 100, 1),
    }


def _largest_dirs(count: int, max_depth: int) -> list[dict]:
    try:
        out = subprocess.run(
            ["du", f"--max-depth={max_depth}", "-h", str(_HOME)],
            capture_output=True, text=True, timeout=60,
        )
    except subprocess.SubprocessError:
        return []
    rows = []
    for line in out.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) == 2:
            rows.append({"size": parts[0], "path": parts[1]})
    # sort by du's human-readable size is unreliable; re-measure top candidates in bytes
    scored = []
    for row in rows:
        b = _du_bytes(Path(row["path"]))
        if b is not None:
            scored.append({"path": row["path"], "size": _fmt_bytes(b), "bytes": b})
    scored.sort(key=lambda r: r["bytes"], reverse=True)
    return scored[:count]


def _expand(paths: list[str]) -> list[Path]:
    return [Path(os.path.expanduser(p)) for p in paths]


def _footprint(paths: list[str]) -> dict:
    result = {}
    for p in _expand(paths):
        b = _du_bytes(p)
        result[str(p)] = {"bytes": b, "human": _fmt_bytes(b)}
    return result


def _log_growth(logs_dir: Path) -> dict:
    if not logs_dir.exists():
        return {"exists": False}
    files = sorted(logs_dir.rglob("*.log*"))
    total = sum(f.stat().st_size for f in files if f.is_file())
    return {
        "exists": True,
        "file_count": len(files),
        "total_bytes": total,
        "total_human": _fmt_bytes(total),
    }


def _postgres_size() -> dict:
    # Best-effort: requires local trust auth or a readable stats view; falls
    # back to reporting "unknown" rather than guessing or requiring sudo.
    try:
        out = subprocess.run(
            ["psql", "-h", "127.0.0.1", "-tAc",
             "SELECT pg_size_pretty(sum(pg_database_size(datname))) FROM pg_database;"],
            capture_output=True, text=True, timeout=10,
        )
        if out.returncode == 0 and out.stdout.strip():
            return {"total_human": out.stdout.strip(), "source": "psql"}
    except (subprocess.SubprocessError, FileNotFoundError):
        pass
    return {"total_human": "unknown (no local psql access from this user)", "source": None}


def build_report() -> dict:
    policy = _load_policy()
    reporting_cfg = policy.get("reporting", {})
    disk = _disk_usage()
    thresholds = policy["thresholds"]["disk"]
    status = "critical" if disk["used_pct"] >= thresholds["critical_pct"] else (
        "warning" if disk["used_pct"] >= thresholds["warning_pct"] else "ok"
    )
    return {
        "disk": {**disk, "status": status, "thresholds": thresholds},
        "largest_dirs": _largest_dirs(
            reporting_cfg.get("largest_dirs_count", 15),
            reporting_cfg.get("du_max_depth", 2),
        ),
        "logs": _log_growth(_ROOT / "logs"),
        "postgres": _postgres_size(),
        "archives": _footprint(["~/archives"]),
        "mt5_footprint": _footprint(["~/.wine", "~/.mt5"]),
        "cache_footprint": _footprint(policy["cache_cleanup"]["safe_paths"]),
    }


def _print_human(report: dict) -> None:
    d = report["disk"]
    print(f"Disk: {_fmt_bytes(d['used'])} used / {_fmt_bytes(d['total'])} total "
          f"({d['used_pct']}%) — status={d['status'].upper()}")
    print(f"  thresholds: warning={d['thresholds']['warning_pct']}% "
          f"critical={d['thresholds']['critical_pct']}%")
    print("\nLargest directories:")
    for row in report["largest_dirs"]:
        print(f"  {row['size']:>8}  {row['path']}")
    logs = report["logs"]
    if logs.get("exists"):
        print(f"\nProject logs: {logs['file_count']} files, {logs['total_human']} total")
    print(f"\nPostgreSQL: {report['postgres']['total_human']}")
    print("\nMT5/Wine footprint:")
    for path, info in report["mt5_footprint"].items():
        print(f"  {info['human']:>8}  {path}")
    print("\nArchives footprint:")
    for path, info in report["archives"].items():
        print(f"  {info['human']:>8}  {path}")
    print("\nRegenerable cache footprint (safe-to-clean candidates):")
    total_cache = sum(i["bytes"] or 0 for i in report["cache_footprint"].values())
    for path, info in report["cache_footprint"].items():
        print(f"  {info['human']:>8}  {path}")
    print(f"  {'---':>8}")
    print(f"  {_fmt_bytes(total_cache):>8}  TOTAL reclaimable (report only — nothing deleted)")


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
