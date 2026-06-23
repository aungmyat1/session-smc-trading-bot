#!/usr/bin/env python3
"""
OPS-01A Health check script.

Checks bot process, tmux session, heartbeat age, log freshness,
disk space, and memory. Exits non-zero if any WARNING or CRITICAL.

Usage:
    python3 scripts/health_check.py          # human-readable
    python3 scripts/health_check.py --json   # JSON output

Alert thresholds:
    heartbeat age   > 10 min  → WARNING
    memory RSS      > 500 MB  → WARNING
    disk free       < 10 %    → WARNING
    MetaAPI status  DISCONNECTED → WARNING
    bot process     missing   → CRITICAL
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).parent.parent
_UTC = timezone.utc

# ── Thresholds ────────────────────────────────────────────────────────────────
_MAX_HEARTBEAT_AGE_S = 600      # 10 minutes
_MAX_MEMORY_MB = 500
_MIN_DISK_FREE_PCT = 10.0
_TMUX_SESSION = "bot"
_BOT_SCRIPT = "bot.py"
_LOG_FILE = _ROOT / "logs" / "bot.log"
_TRADE_LOG = _ROOT / "logs" / "trades.jsonl"


# ── Result accumulator ────────────────────────────────────────────────────────

class Health:
    OK = "OK"
    WARN = "WARNING"
    CRIT = "CRITICAL"

    def __init__(self) -> None:
        self._checks: list[dict] = []

    def add(self, name: str, level: str, value: str, detail: str = "") -> None:
        self._checks.append({"name": name, "level": level, "value": value, "detail": detail})
        icon = "✅" if level == self.OK else ("⚠️ " if level == self.WARN else "🔴")
        suffix = f"  ({detail})" if detail else ""
        print(f"  {icon}  [{level:<8}]  {name}: {value}{suffix}")

    def worst(self) -> str:
        levels = {self.OK: 0, self.WARN: 1, self.CRIT: 2}
        return max(self._checks, key=lambda c: levels.get(c["level"], 0))["level"] \
            if self._checks else self.OK

    def checks(self) -> list[dict]:
        return list(self._checks)

    def exit_code(self) -> int:
        w = self.worst()
        return 0 if w == self.OK else (1 if w == self.WARN else 2)


# ── Individual checks ─────────────────────────────────────────────────────────

def check_tmux(h: Health) -> bool:
    """Is the tmux session named 'bot' running?"""
    result = subprocess.run(
        ["tmux", "ls"], capture_output=True, text=True
    )
    sessions = result.stdout
    running = _TMUX_SESSION in sessions
    if running:
        h.add("tmux session 'bot'", Health.OK, "running")
    else:
        h.add("tmux session 'bot'", Health.CRIT, "NOT FOUND",
              f"start: tmux new-session -d -s {_TMUX_SESSION} 'python3 bot.py 2>&1 | tee logs/bot.log'")
    return running


def check_bot_process(h: Health) -> bool:
    """Is python3 bot.py running as a process?"""
    result = subprocess.run(
        ["pgrep", "-f", _BOT_SCRIPT], capture_output=True, text=True
    )
    pids = result.stdout.strip().splitlines()
    if pids:
        h.add("bot process", Health.OK, f"running (pid={pids[0]})")
        return True
    else:
        h.add("bot process", Health.CRIT, "NOT RUNNING",
              "run: tmux new-session -d -s bot 'python3 bot.py 2>&1 | tee logs/bot.log'")
        return False


def check_heartbeat_age(h: Health) -> None:
    """How old is the last HEARTBEAT line in bot.log?"""
    if not _LOG_FILE.exists():
        h.add("heartbeat age", Health.WARN, "no log file yet", "bot may not have started")
        return

    last_hb_ts: "datetime | None" = None
    try:
        with open(_LOG_FILE) as f:
            for line in f:
                if "HEARTBEAT" in line:
                    # Line format: 2026-06-21 08:05:00,123  INFO  bot  [HEARTBEAT]…
                    m = re.match(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", line)
                    if m:
                        last_hb_ts = datetime.strptime(
                            m.group(1), "%Y-%m-%d %H:%M:%S"
                        ).replace(tzinfo=_UTC)
    except Exception as e:
        h.add("heartbeat age", Health.WARN, f"parse error: {e}")
        return

    if last_hb_ts is None:
        h.add("heartbeat age", Health.WARN, "no heartbeat found yet",
              "bot started <5 min ago, or off-hours sleep")
        return

    age_s = int((datetime.now(_UTC) - last_hb_ts).total_seconds())
    age_min = age_s // 60
    if age_s <= _MAX_HEARTBEAT_AGE_S:
        h.add("heartbeat age", Health.OK, f"{age_min}m {age_s%60}s ago",
              last_hb_ts.strftime("%H:%M UTC"))
    else:
        h.add("heartbeat age", Health.WARN, f"{age_min}m old (> 10m threshold)",
              f"last: {last_hb_ts.strftime('%H:%M UTC')}")


def check_log_freshness(h: Health) -> None:
    """When was bot.log last written?"""
    if not _LOG_FILE.exists():
        h.add("log freshness", Health.WARN, "logs/bot.log does not exist")
        return
    mtime = _LOG_FILE.stat().st_mtime
    age_s = int(time.time() - mtime)
    age_min = age_s // 60
    size_kb = _LOG_FILE.stat().st_size // 1024
    if age_s < 600:
        h.add("log freshness", Health.OK, f"updated {age_min}m ago  size={size_kb}KB")
    else:
        h.add("log freshness", Health.WARN, f"last write {age_min}m ago",
              "bot may be stalled or off-hours sleeping")


def check_metaapi_status(h: Health) -> None:
    """Read connection status from the last HEARTBEAT block (multi-line)."""
    if not _LOG_FILE.exists():
        h.add("MetaAPI status", Health.WARN, "no log yet")
        return

    # Heartbeat is logged as a multi-line message (logger.info(msg) with \n).
    # Collect all lines in the last heartbeat block by finding the last
    # [HEARTBEAT] marker and joining the following lines until the next log entry.
    lines: list[str] = []
    try:
        with open(_LOG_FILE) as f:
            lines = f.readlines()
    except Exception:
        pass

    if not lines:
        h.add("MetaAPI status", Health.WARN, "no heartbeat to read from")
        return

    # Find last occurrence of [HEARTBEAT] and collect until next dated log line
    last_hb_block = ""
    _ts_pattern = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}")
    i = len(lines) - 1
    while i >= 0:
        if "[HEARTBEAT]" in lines[i]:
            # Collect this line + following lines until next log timestamp
            block_lines = [lines[i]]
            j = i + 1
            while j < len(lines) and not _ts_pattern.match(lines[j]):
                block_lines.append(lines[j])
                j += 1
            last_hb_block = " ".join(block_lines)
            break
        i -= 1

    if not last_hb_block:
        h.add("MetaAPI status", Health.WARN, "no heartbeat to read from")
        return

    if "connection_status=CONNECTED" in last_hb_block:
        h.add("MetaAPI status", Health.OK, "CONNECTED")
    elif "connection_status=DISCONNECTED" in last_hb_block:
        h.add("MetaAPI status", Health.WARN, "DISCONNECTED",
              "SDK will auto-reconnect; check logs if persists >5 min")
    else:
        h.add("MetaAPI status", Health.WARN, "unknown (heartbeat format changed?)")


def check_disk(h: Health) -> None:
    """Check free disk space on /."""
    total, used, free = shutil.disk_usage("/")
    free_pct = free / total * 100
    free_gb = free / (1024 ** 3)
    if free_pct >= _MIN_DISK_FREE_PCT:
        h.add("disk free", Health.OK, f"{free_gb:.1f} GB ({free_pct:.1f}%)")
    else:
        h.add("disk free", Health.WARN, f"{free_gb:.1f} GB ({free_pct:.1f}%) < 10% threshold",
              "clean up logs or expand disk")


def check_memory(h: Health) -> None:
    """Check bot process memory (RSS) and system available RAM."""
    # System available
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemAvailable:"):
                    avail_mb = int(line.split()[1]) // 1024
                    break
            else:
                avail_mb = -1
    except Exception:
        avail_mb = -1

    # Bot process RSS
    bot_rss_mb = -1
    try:
        result = subprocess.run(
            ["pgrep", "-f", _BOT_SCRIPT], capture_output=True, text=True
        )
        pids = result.stdout.strip().splitlines()
        if pids:
            with open(f"/proc/{pids[0]}/status") as f:
                for line in f:
                    if line.startswith("VmRSS:"):
                        bot_rss_mb = int(line.split()[1]) // 1024
                        break
    except Exception:
        pass

    if bot_rss_mb >= 0:
        level = Health.OK if bot_rss_mb <= _MAX_MEMORY_MB else Health.WARN
        detail = f"system available: {avail_mb}MB" if avail_mb >= 0 else ""
        h.add("memory (bot RSS)", level,
              f"{bot_rss_mb} MB" + (" > 500MB threshold" if bot_rss_mb > _MAX_MEMORY_MB else ""),
              detail)
    else:
        h.add("memory (bot RSS)", Health.OK,
              f"bot not running — system available: {avail_mb}MB" if avail_mb >= 0
              else "could not read")


def check_live_trading_guard(h: Health) -> None:
    """Verify .env has LIVE_TRADING=false (last effective value)."""
    env_path = _ROOT / ".env"
    if not env_path.exists():
        h.add("LIVE_TRADING guard", Health.WARN, ".env missing")
        return
    live = "false"
    for line in env_path.read_text().splitlines():
        stripped = line.strip()
        if stripped.startswith("LIVE_TRADING="):
            live = stripped.split("=", 1)[1].strip().lower()
    if live == "false":
        h.add("LIVE_TRADING guard", Health.OK, "false")
    else:
        h.add("LIVE_TRADING guard", Health.CRIT, f"LIVE_TRADING={live} — MUST be false",
              "edit .env immediately and restart bot")


def check_trade_log(h: Health) -> None:
    """Verify trades.jsonl exists and is valid JSONL."""
    if not _TRADE_LOG.exists():
        h.add("trade log", Health.OK, "not yet created (no signals since start)")
        return
    lines = _TRADE_LOG.read_text().strip().splitlines()
    bad = 0
    for line in lines:
        try:
            json.loads(line)
        except Exception:
            bad += 1
    size_kb = _TRADE_LOG.stat().st_size // 1024
    if bad == 0:
        h.add("trade log", Health.OK, f"{len(lines)} events  {size_kb}KB  all valid JSON")
    else:
        h.add("trade log", Health.WARN, f"{bad}/{len(lines)} lines are malformed JSON",
              "log may be corrupted — investigate before next restart")


# ── Main ──────────────────────────────────────────────────────────────────────

def run() -> Health:
    now = datetime.now(_UTC)
    h = Health()

    print()
    print("=" * 62)
    print(f"  Health Check  {now.strftime('%Y-%m-%dT%H:%M UTC')}")
    print("=" * 62)

    print("\n[Process]")
    check_tmux(h)
    check_bot_process(h)

    print("\n[Connectivity]")
    check_metaapi_status(h)
    check_heartbeat_age(h)
    check_log_freshness(h)

    print("\n[Resources]")
    check_disk(h)
    check_memory(h)

    print("\n[Safety]")
    check_live_trading_guard(h)
    check_trade_log(h)

    worst = h.worst()
    print()
    print("=" * 62)
    icon = "✅" if worst == Health.OK else ("⚠️ " if worst == Health.WARN else "🔴")
    print(f"  VERDICT: {icon} {worst}")
    print("=" * 62)
    print()

    return h


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="output JSON")
    args = parser.parse_args()

    h = run()

    if args.json:
        print(json.dumps({
            "ts": datetime.now(_UTC).isoformat(),
            "verdict": h.worst(),
            "checks": h.checks(),
        }, indent=2))

    sys.exit(h.exit_code())
