"""
Strategy Stats — per-strategy signal and trade contribution report.

Reads from:
  logs/st_a2_demo_trades.jsonl    (ST-A2 demo trades)
  logs/adaptive_trades.jsonl      (Adaptive engine trades)
  logs/st_a2_runner.log           (runner tick/signal log)

Usage:
    python3 scripts/strategy_stats.py
    python3 scripts/strategy_stats.py --days 7
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

_JOURNAL_PATHS = [
    _ROOT / "logs" / "st_a2_demo_trades.jsonl",
    _ROOT / "logs" / "adaptive_trades.jsonl",
]
_RUNNER_LOG = _ROOT / "logs" / "st_a2_runner.log"


def _load_journal_trades(days: int) -> list[dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    trades = []
    for path in _JOURNAL_PATHS:
        if not path.exists():
            continue
        with path.open() as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                ts_str = rec.get("timestamp", "")
                try:
                    ts = datetime.fromisoformat(ts_str)
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                    if ts >= cutoff:
                        trades.append(rec)
                except (ValueError, TypeError):
                    trades.append(rec)
    return trades


def _count_signals_from_log(days: int) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    if not _RUNNER_LOG.exists():
        return counts
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    sig_re = re.compile(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*SIGNAL\s+(\w+)")
    with _RUNNER_LOG.open() as fh:
        for line in fh:
            m = sig_re.search(line)
            if not m:
                continue
            try:
                ts = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S").replace(
                    tzinfo=timezone.utc
                )
                if ts >= cutoff:
                    counts["ST-A2"] += 1
            except ValueError:
                pass
    return counts


def _strategy_breakdown(trades: list[dict]) -> dict[str, dict]:
    stats: dict[str, dict] = defaultdict(
        lambda: {"opened": 0, "closed": 0, "wins": 0, "losses": 0, "total_r": 0.0}
    )
    for t in trades:
        strat = t.get("strategy", "unknown")
        if t.get("record_type") == "open":
            stats[strat]["opened"] += 1
        elif t.get("record_type") == "close":
            stats[strat]["closed"] += 1
            r = t.get("result_R", 0.0) or 0.0
            stats[strat]["total_r"] += r
            if r > 0:
                stats[strat]["wins"] += 1
            else:
                stats[strat]["losses"] += 1
    return dict(stats)


def _print_report(days: int) -> None:
    trades = _load_journal_trades(days)
    signals = _count_signals_from_log(days)
    by_strat = _strategy_breakdown(trades)

    total_opens = sum(1 for t in trades if t.get("record_type") == "open")
    total_closes = sum(1 for t in trades if t.get("record_type") == "close")
    all_r = [
        t.get("result_R", 0) or 0 for t in trades if t.get("record_type") == "close"
    ]
    wins = sum(1 for r in all_r if r > 0)
    pf_denom = sum(abs(r) for r in all_r if r < 0)
    pf_numer = sum(r for r in all_r if r > 0)
    pf = round(pf_numer / pf_denom, 2) if pf_denom else float("inf")

    print()
    print("=" * 60)
    print(f"  STRATEGY STATS  (last {days} day{'s' if days != 1 else ''})")
    print("=" * 60)
    print(f"  Total signals logged: {sum(signals.values())}")
    print(f"  Total trades opened:  {total_opens}")
    print(f"  Total trades closed:  {total_closes}")
    if total_closes:
        wr = round(wins / total_closes * 100, 1)
        avg_r = round(sum(all_r) / total_closes, 3)
        print(f"  Win rate:             {wins}/{total_closes} = {wr}%")
        print(f"  Profit factor:        {pf}")
        print(f"  Avg R per trade:      {avg_r}")

    print()
    print("  BY STRATEGY:")
    print(
        f"  {'Strategy':<18} {'Signals':>7} {'Opened':>7} {'Closed':>7} "
        f"{'W':>4} {'L':>4} {'Sum R':>7}"
    )
    print("  " + "-" * 56)

    all_strats = sorted(set(list(by_strat.keys()) + list(signals.keys())))
    for strat in all_strats:
        s = by_strat.get(strat, {})
        sig_count = signals.get(strat, 0)
        opened = s.get("opened", 0)
        closed = s.get("closed", 0)
        wins_s = s.get("wins", 0)
        losses_s = s.get("losses", 0)
        total_r_s = round(s.get("total_r", 0.0), 2)
        print(
            f"  {strat:<18} {sig_count:>7} {opened:>7} {closed:>7} "
            f"{wins_s:>4} {losses_s:>4} {total_r_s:>7.2f}"
        )

    print()
    print("=" * 60)
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Strategy contribution stats")
    parser.add_argument("--days", type=int, default=1)
    args = parser.parse_args()
    _print_report(args.days)


if __name__ == "__main__":
    main()
