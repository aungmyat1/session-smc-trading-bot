#!/usr/bin/env python3
"""Lightweight memory health check for the shared dev/production VPS.

One-shot: prints JSON to stdout. Import get_memory_health() to embed
elsewhere (e.g. a dashboard endpoint). No dependencies beyond stdlib.
"""
from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from dev_process_audit import classify, _ps_snapshot  # noqa: E402

RAM_WARN_PCT = 80
SWAP_WARN_PCT = 50
EXT_HOST_WARN_MB = 2048


def _meminfo() -> dict:
    info = {}
    with open("/proc/meminfo") as f:
        for line in f:
            m = re.match(r"(\w+):\s+(\d+)", line)
            if m:
                info[m.group(1)] = int(m.group(2))  # kB
    return info


def get_memory_health() -> dict:
    mi = _meminfo()
    ram_total = mi.get("MemTotal", 1)
    ram_avail = mi.get("MemAvailable", 0)
    ram_used_pct = round((ram_total - ram_avail) / ram_total * 100, 1)

    swap_total = mi.get("SwapTotal", 0)
    swap_free = mi.get("SwapFree", 0)
    swap_used_pct = round((swap_total - swap_free) / swap_total * 100, 1) if swap_total else 0.0

    procs = _ps_snapshot()
    data = classify(procs)
    ext_hosts = [p for p in procs if "extensionHost" in p["cmd"]]
    ext_host_max_mb = round(max((p["rss_kb"] for p in ext_hosts), default=0) / 1024, 1)
    claude_sessions = [p for p in procs if re.search(r"native-binary/claude", p["cmd"])]

    warnings = []
    if ram_used_pct > RAM_WARN_PCT:
        warnings.append(f"RAM usage {ram_used_pct}% > {RAM_WARN_PCT}%")
    if swap_used_pct > SWAP_WARN_PCT:
        warnings.append(f"Swap usage {swap_used_pct}% > {SWAP_WARN_PCT}%")
    if ext_host_max_mb > EXT_HOST_WARN_MB:
        warnings.append(f"Extension host RSS {ext_host_max_mb}MB > {EXT_HOST_WARN_MB}MB")
    if len(claude_sessions) > 1:
        warnings.append(f"{len(claude_sessions)} duplicate claude sessions running")
    if data["dev_orphan"]:
        warnings.append(f"{len(data['dev_orphan'])} orphaned dev processes present")

    return {
        "ram_used_pct": ram_used_pct,
        "swap_used_pct": swap_used_pct,
        "extension_host_max_rss_mb": ext_host_max_mb,
        "claude_session_count": len(claude_sessions),
        "dev_orphan_count": len(data["dev_orphan"]),
        "production_process_count": len(data["production"]),
        "warnings": warnings,
        "ok": not warnings,
    }


if __name__ == "__main__":
    print(json.dumps(get_memory_health(), indent=2))
