#!/usr/bin/env python3
"""
daily_spread_report.py — concise daily spread collection report.

Usage:
    python3 scripts/daily_spread_report.py

Prints a summary of today's collection progress and overall status.
Read-only — does not modify any files.
"""
import csv
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, date, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
CSV = _ROOT / "research" / "spread_samples.csv"


def _tmux_running(name: str) -> bool:
    try:
        r = subprocess.run(["tmux", "ls"], capture_output=True, text=True)
        return name in r.stdout
    except FileNotFoundError:
        return False


def main() -> None:
    now = datetime.now(timezone.utc)
    today_str = now.strftime("%Y-%m-%d")

    print("=" * 50)
    print("Spread Collection Daily Report")
    print(f"{now.strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 50)
    print()

    # ── Process status ────────────────────────────────────────────────────────
    spreads_up = _tmux_running("spreads")
    bot_up = _tmux_running("bot")
    print(f"Collector (tmux 'spreads'): {'RUNNING' if spreads_up else 'STOPPED ⚠️'}")
    print(f"Bot       (tmux 'bot'):     {'RUNNING' if bot_up else 'STOPPED ⚠️'}")
    print()

    if not CSV.exists():
        print("CSV not found — collection not started.")
        sys.exit(1)

    # ── Load data ─────────────────────────────────────────────────────────────
    rows = list(csv.DictReader(CSV.open()))
    if not rows:
        print("CSV is empty — no samples collected yet.")
        sys.exit(1)

    today_rows = [r for r in rows if r["time_utc"].startswith(today_str)]
    total_rows = len(rows)
    rows_today = len(today_rows)

    # Session counts (killzone rows only)
    by_sess = defaultdict(list)
    by_sess_today = defaultdict(list)
    sess_days: dict[str, set] = defaultdict(set)

    for r in rows:
        sess = r["session"]
        if sess != "off":
            by_sess[sess].append(r)
            sess_days[sess].add(r["time_utc"][:10])
        if r["time_utc"].startswith(today_str) and sess != "off":
            by_sess_today[sess].append(r)

    london_total = len(by_sess["london"])
    ny_total = len(by_sess["new_york"])
    london_today = len(by_sess_today["london"])
    ny_today = len(by_sess_today["new_york"])

    london_days = len(sess_days["london"])
    ny_days = len(sess_days["new_york"])

    # Latest timestamp
    times = sorted(set(r["time_utc"] for r in rows))
    latest = times[-1] if times else "—"
    latest_dt = datetime.fromisoformat(latest)
    age_seconds = (now - latest_dt).total_seconds()

    # Symbol coverage
    symbols_seen = set(r["symbol"] for r in (today_rows if today_rows else rows))
    expected = {"EURUSD", "GBPUSD", "USDJPY", "AUDUSD"}
    missing = expected - symbols_seen

    # ── Output ────────────────────────────────────────────────────────────────
    print(f"Rows today:          {rows_today:,}")
    print(f"Rows total:          {total_rows:,}")
    print()
    print(f"London:              {london_total:,} samples ({london_days}/5 sessions)")
    print(f"  Today:             {london_today:,}")
    print()
    print(f"New York:            {ny_total:,} samples ({ny_days}/5 sessions)")
    print(f"  Today:             {ny_today:,}")
    print()
    print(f"Symbol coverage:     {', '.join(sorted(symbols_seen))} "
          f"{'✅' if not missing else f'⚠️ missing: {missing}'}")
    print()
    print(f"Latest sample:       {latest_dt.strftime('%Y-%m-%d %H:%M')} UTC")
    print(f"Sample age:          {age_seconds / 60:.1f} min ago")
    print()

    # ── Gate progress ─────────────────────────────────────────────────────────
    gate_7k = total_rows >= 7000
    gate_sessions = london_days >= 5 and ny_days >= 5
    gate_met = gate_7k and gate_sessions

    print(f"Gate progress:")
    print(f"  London sessions:   {london_days}/5  {'✅' if london_days >= 5 else '⏳'}")
    print(f"  NY sessions:       {ny_days}/5  {'✅' if ny_days >= 5 else '⏳'}")
    print(f"  ≥7,000 rows:       {total_rows:,}/7,000  {'✅' if gate_7k else '⏳'}")
    print()

    # ── Health verdict ────────────────────────────────────────────────────────
    old_sample = age_seconds > 300  # > 5 min stale
    issues = []
    if not spreads_up:
        issues.append("collector not running")
    if old_sample:
        issues.append(f"last sample {age_seconds / 60:.0f}min ago (expected <2min)")
    if missing:
        issues.append(f"missing symbols: {missing}")

    if issues:
        print(f"Status:              ⚠️ WARNING — {'; '.join(issues)}")
    elif gate_met:
        print("Status:              ✅ GATE MET — ready for cost revalidation")
    else:
        days_left = max(5 - london_days, 5 - ny_days)
        print(f"Status:              ✅ HEALTHY — {days_left} more trading day(s) to gate")

    print()

    if not gate_met:
        print("Next action:         Continue collecting. Run this report each morning.")
        print("                     Run check: python3 scripts/check_phase2_completion.py")
    else:
        print("Next action:         Run python3 scripts/check_phase2_completion.py")
        print("                     Then proceed to E6 cost revalidation.")

    print()
    print("=" * 50)


if __name__ == "__main__":
    main()
