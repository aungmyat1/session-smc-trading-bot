#!/usr/bin/env python3
"""Quick status check for the running spread capture."""

from __future__ import annotations

import csv
import statistics
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = _ROOT / "research" / "spread_samples.csv"
LOG_PATH = _ROOT / "logs" / "spread_capture.log"


def load_rows(path: Path = CSV_PATH) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def count_session_days(rows: list[dict[str, str]]) -> dict[str, set[str]]:
    days: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        session = row.get("session", "")
        if session == "off":
            continue
        ts = row.get("time_utc", "")
        if ts:
            days[session].add(ts[:10])
    return days


def main() -> int:
    now = datetime.now(timezone.utc)
    rows = load_rows()
    session_days = count_session_days(rows)

    print(f"Spread Capture Status — {now.strftime('%Y-%m-%d %H:%M UTC')}")
    print()

    try:
        result = subprocess.run(["tmux", "ls"], capture_output=True, text=True, check=False)
        running = "spreads" in result.stdout
    except FileNotFoundError:
        running = False
    print(f"  tmux 'spreads': {'✅ RUNNING' if running else '❌ NOT FOUND'}")

    if not CSV_PATH.exists():
        print(f"  CSV: ❌ not found at {CSV_PATH}")
        return 1

    print(f"  CSV rows: {len(rows)}")
    if not rows:
        print("  No data yet.")
        return 0

    times = sorted({row["time_utc"] for row in rows if row.get("time_utc")})
    print(f"  Span: {times[0]} → {times[-1]}")

    parsed = [datetime.fromisoformat(t) for t in times]
    if len(parsed) > 1:
        gaps = [(parsed[i] - parsed[i - 1]).total_seconds() for i in range(1, len(parsed))]
        print(
            f"  Poll interval: avg={statistics.mean(gaps):.0f}s  "
            f"max={max(gaps):.0f}s  gaps>90s: {sum(1 for g in gaps if g > 90)}"
        )

    london_days = len(session_days.get("london", set()))
    ny_days = len(session_days.get("new_york", set()))
    gate_met = london_days >= 5 and ny_days >= 5

    print()
    print("  Session coverage:")
    print(f"    London:   {london_days}/5  {sorted(session_days.get('london', set()))}")
    print(f"    New York: {ny_days}/5  {sorted(session_days.get('new_york', set()))}")
    print(
        f"    Gate (5+5): {'✅ MET' if gate_met else f'⏳ {max(0, 5 - london_days)}L + {max(0, 5 - ny_days)}NY remaining'}"
    )
    print()

    spreads: dict[tuple[str, str], list[float]] = defaultdict(list)
    for row in rows:
        session = row.get("session", "")
        if session == "off":
            continue
        symbol = row.get("symbol", "")
        try:
            spreads[(symbol, session)].append(float(row["spread_pips"]))
        except (TypeError, ValueError, KeyError):
            continue

    print("  Killzone spread averages (pip):")
    print(f"  {'Symbol':<8} {'Session':<10} {'n':>5} {'Avg':>6} {'Med':>6} {'P95':>6} {'Max':>6}")
    for symbol in ("EURUSD", "GBPUSD", "USDJPY", "AUDUSD"):
        for session in ("london", "new_york"):
            values = spreads.get((symbol, session), [])
            if not values:
                continue
            values_sorted = sorted(values)
            p95 = values_sorted[max(0, min(len(values_sorted) - 1, int(len(values_sorted) * 0.95)))]
            print(
                f"  {symbol:<8} {session:<10} {len(values):>5} "
                f"{statistics.mean(values):>6.2f} {statistics.median(values):>6.2f} "
                f"{p95:>6.2f} {max(values):>6.2f}"
            )

    if not gate_met:
        print()
        print("  No action needed. Run: python3 scripts/spread_status.py each morning.")
    elif LOG_PATH.exists():
        print()
        print(f"  Log: {LOG_PATH}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
