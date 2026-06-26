#!/usr/bin/env python3
"""Gate check for Phase-2 spread capture completion."""

from __future__ import annotations

import csv
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = _ROOT / "research" / "spread_samples.csv"

MIN_LONDON_SESSIONS = 5
MIN_NY_SESSIONS = 5
MIN_ROWS = 7_000


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

    if not rows:
        print(f"ERROR: {CSV_PATH} not found or empty.")
        print("NOT_READY")
        return 1

    total = len(rows)
    session_days = count_session_days(rows)
    london_days = len(session_days.get("london", set()))
    ny_days = len(session_days.get("new_york", set()))

    gate_london = london_days >= MIN_LONDON_SESSIONS
    gate_ny = ny_days >= MIN_NY_SESSIONS
    gate_rows = total >= MIN_ROWS
    ready = gate_london and gate_ny and gate_rows

    print(f"Phase 2 Completion Check — {now.strftime('%Y-%m-%d %H:%M UTC')}")
    print()
    print(f"  London sessions:  {london_days}/{MIN_LONDON_SESSIONS}  {'PASS' if gate_london else 'FAIL'}")
    print(f"  NY sessions:      {ny_days}/{MIN_NY_SESSIONS}  {'PASS' if gate_ny else 'FAIL'}")
    print(f"  Total rows:       {total:,}/{MIN_ROWS:,}  {'PASS' if gate_rows else 'FAIL'}")
    print()

    if ready:
        print("READY_FOR_COST_REVALIDATION")
        print()
        print("Next steps:")
        print("  1. Stop capture:  tmux send-keys -t spreads C-c")
        print("  2. Build model:   python3 scripts/build_cost_model.py")
        print("  3. Export costs:  python3 scripts/export_spread_limits.py")
        print("  4. Run backtest:  bash scripts/run_e6_revalidation.sh")
        return 0

    remaining = []
    if not gate_london:
        remaining.append(f"{max(0, MIN_LONDON_SESSIONS - london_days)} more London session(s)")
    if not gate_ny:
        remaining.append(f"{max(0, MIN_NY_SESSIONS - ny_days)} more NY session(s)")
    if not gate_rows:
        remaining.append(f"{max(0, MIN_ROWS - total):,} more rows")
    print("NOT_READY")
    print()
    print(f"  Remaining: {', '.join(remaining)}")
    print()
    print("  Continue collecting. Monitor: python3 scripts/spread_status.py")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
