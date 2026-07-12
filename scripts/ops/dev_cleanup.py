#!/usr/bin/env python3
"""Safely terminate orphaned dev-tooling processes (DEV_ORPHAN class only).

Dry-run by default. Never touches PRODUCTION or DEV_ACTIVE processes -
enforced twice: by classify() and again here as a hard safety net.

Usage:
  python3 dev_cleanup.py                # dry-run, prints what would die
  python3 dev_cleanup.py --yes          # actually terminate, with logging
"""
from __future__ import annotations

import os
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from dev_process_audit import classify, PROTECTED_PATTERNS, _matches_any  # noqa: E402

LOG_PATH = Path(__file__).resolve().parent.parent.parent / "logs" / "dev_cleanup.log"
SIGTERM_TIMEOUT_S = 5


def _log(msg: str) -> None:
    line = f"{datetime.now(timezone.utc).isoformat()} {msg}"
    print(line)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a") as f:
        f.write(line + "\n")


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def main() -> None:
    dry_run = "--yes" not in sys.argv
    data = classify()
    orphans = data["dev_orphan"]

    if not orphans:
        _log("cleanup: no orphaned dev processes found")
        return

    # Hard safety net: never act on anything matching a protected pattern,
    # regardless of how classify() labeled it.
    orphans = [p for p in orphans if not _matches_any(p["cmd"], PROTECTED_PATTERNS)]
    pids = [p["pid"] for p in orphans]

    _log(f"cleanup: {'DRY-RUN' if dry_run else 'EXECUTING'} target pids={pids}")
    for p in orphans:
        _log(f"  candidate pid={p['pid']} rss={p['rss_kb']/1024:.1f}MB up={p['etimes']}s cmd={p['cmd'][:80]}")

    if dry_run:
        _log("cleanup: dry-run complete, nothing terminated (pass --yes to execute)")
        return

    for pid in pids:
        if not _pid_alive(pid):
            continue
        try:
            os.kill(pid, signal.SIGTERM)
            _log(f"cleanup: SIGTERM -> pid={pid}")
        except OSError as exc:
            _log(f"cleanup: SIGTERM failed pid={pid} err={exc}")

    deadline = time.time() + SIGTERM_TIMEOUT_S
    while time.time() < deadline and any(_pid_alive(pid) for pid in pids):
        time.sleep(0.5)

    for pid in pids:
        if _pid_alive(pid):
            try:
                os.kill(pid, signal.SIGKILL)
                _log(f"cleanup: SIGKILL -> pid={pid} (SIGTERM timed out)")
            except OSError as exc:
                _log(f"cleanup: SIGKILL failed pid={pid} err={exc}")

    _log("cleanup: done")


if __name__ == "__main__":
    main()
