#!/usr/bin/env python3
"""
check_phase2_completion.py — gate check for Phase 2 spread collection.

Criteria (all three required):
  - >= 5 distinct London session days
  - >= 5 distinct New York session days
  - >= 7,000 total rows in spread_samples.csv

Output:
  Prints NOT_READY or READY_FOR_COST_REVALIDATION

Exit code:
  0 = ready (all gates met)
  1 = not ready
"""
import csv
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
CSV = _ROOT / "research" / "spread_samples.csv"

MIN_LONDON_SESSIONS = 5
MIN_NY_SESSIONS = 5
MIN_ROWS = 7_000


def main() -> int:
    now = datetime.now(timezone.utc)

    if not CSV.exists():
        print(f"ERROR: {CSV} not found.")
        print("NOT_READY")
        return 1

    rows = list(csv.DictReader(CSV.open()))
    total = len(rows)

    sess_days: dict[str, set] = defaultdict(set)
    for r in rows:
        if r["session"] != "off":
            sess_days[r["session"]].add(r["time_utc"][:10])

    london_days = len(sess_days["london"])
    ny_days = len(sess_days["new_york"])

    gate_london = london_days >= MIN_LONDON_SESSIONS
    gate_ny = ny_days >= MIN_NY_SESSIONS
    gate_rows = total >= MIN_ROWS
    all_pass = gate_london and gate_ny and gate_rows

    print(f"Phase 2 Completion Check — {now.strftime('%Y-%m-%d %H:%M UTC')}")
    print()
    print(f"  London sessions:  {london_days}/{MIN_LONDON_SESSIONS}  "
          f"{'PASS' if gate_london else 'FAIL'}")
    print(f"  NY sessions:      {ny_days}/{MIN_NY_SESSIONS}  "
          f"{'PASS' if gate_ny else 'FAIL'}")
    print(f"  Total rows:       {total:,}/{MIN_ROWS:,}  "
          f"{'PASS' if gate_rows else 'FAIL'}")
    print()

    if all_pass:
        print("READY_FOR_COST_REVALIDATION")
        print()
        print("Next steps:")
        print("  1. Stop capture:  tmux send-keys -t spreads C-c")
        print("  2. Fill costs:    config/costs.json → profiles.vantage_measured")
        print("  3. Set profile:   active_profile = 'vantage_measured'")
        print("  4. Run backtest:  python3 scripts/backtest_session_liquidity.py")
        print("  5. Apply gate:    docs/OPS02_REVISED_GATE.md — E6 decision table")
        return 0
    else:
        remaining = []
        if not gate_london:
            remaining.append(f"{MIN_LONDON_SESSIONS - london_days} more London session(s)")
        if not gate_ny:
            remaining.append(f"{MIN_NY_SESSIONS - ny_days} more NY session(s)")
        if not gate_rows:
            remaining.append(f"{MIN_ROWS - total:,} more rows")
        print("NOT_READY")
        print()
        print(f"  Remaining: {', '.join(remaining)}")
        print()
        print("  Continue collecting. Expected gate: ~2026-06-30 14:00 UTC")
        print("  Monitor: python3 scripts/daily_spread_report.py")
        return 1


if __name__ == "__main__":
    sys.exit(main())
