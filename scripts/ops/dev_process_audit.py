#!/usr/bin/env python3
"""Audit and classify processes on a shared dev/production VPS.

Classifies every process into:
  PRODUCTION  - matches a protected pattern, never touched
  DEV_ACTIVE  - dev tooling (claude/codex/vscode-server/mcp) attached to a
                live code-server session
  DEV_ORPHAN  - dev tooling reparented to init (ppid=1) after its parent
                extension host crashed/restarted - safe to clean up
  OTHER       - system daemons, unrelated processes (not reported in detail)

Read-only. Prints a table + JSON summary. Import `classify()` from the
cleanup utility instead of duplicating this logic.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys

PROTECTED_PATTERNS = [
    r"postgres",
    r"run_strategy_demo\.py",
    r"status_server:app",
    r"redis-server",
    r"nginx",
    r"smc-demo-runner",
]

DEV_PATTERNS = [
    r"anthropic\.claude-code.*native-binary/claude",
    r"openai\.chatgpt.*codex",
    r"mcp-server-circleci",
    r"pionex-trade-mcp",
    r"npm exec @",
    r"vscode-server.*bootstrap-fork.*extensionHost",
    r"vscode-server.*(language-features|languageserver|pylance)",
]

SESSION_ROOT_PATTERN = r"server/out/server-main\.js"


def _ps_snapshot() -> list[dict]:
    out = subprocess.run(
        ["ps", "-eo", "pid,ppid,etimes,rss,vsz,pcpu,cmd", "--no-headers"],
        capture_output=True, text=True, timeout=10,
    ).stdout
    procs = []
    for line in out.splitlines():
        parts = line.strip().split(None, 6)
        if len(parts) < 7:
            continue
        pid, ppid, etimes, rss, vsz, pcpu, cmd = parts
        procs.append({
            "pid": int(pid), "ppid": int(ppid), "etimes": int(etimes),
            "rss_kb": int(rss), "vsz_kb": int(vsz), "pcpu": float(pcpu), "cmd": cmd,
        })
    return procs


def _matches_any(cmd: str, patterns: list[str]) -> bool:
    return any(re.search(p, cmd) for p in patterns)


def classify(procs: list[dict] | None = None) -> dict:
    procs = procs if procs is not None else _ps_snapshot()
    by_pid = {p["pid"]: p for p in procs}
    session_roots = {p["pid"] for p in procs if _matches_any(p["cmd"], [SESSION_ROOT_PATTERN])}

    def is_under_session_root(pid: int, _seen: set | None = None) -> bool:
        _seen = _seen or set()
        if pid in _seen or pid not in by_pid:
            return False
        _seen.add(pid)
        if pid in session_roots:
            return True
        return is_under_session_root(by_pid[pid]["ppid"], _seen)

    result = {"production": [], "dev_active": [], "dev_orphan": [], "other": []}
    for p in procs:
        if _matches_any(p["cmd"], PROTECTED_PATTERNS):
            result["production"].append(p)
        elif _matches_any(p["cmd"], DEV_PATTERNS):
            if is_under_session_root(p["pid"]):
                result["dev_active"].append(p)
            else:
                result["dev_orphan"].append(p)
        else:
            result["other"].append(p)
    return result


def main() -> None:
    data = classify()
    for label in ("production", "dev_active", "dev_orphan"):
        rows = sorted(data[label], key=lambda p: -p["rss_kb"])
        print(f"\n== {label.upper()} ({len(rows)}) ==")
        for p in rows:
            print(f"  pid={p['pid']:<7} ppid={p['ppid']:<7} rss={p['rss_kb']/1024:>7.1f}MB "
                  f"vsz={p['vsz_kb']/1024:>8.1f}MB cpu={p['pcpu']:>5.1f}% up={p['etimes']}s  {p['cmd'][:90]}")
    if "--json" in sys.argv:
        print(json.dumps(data, indent=2))


if __name__ == "__main__":
    main()
