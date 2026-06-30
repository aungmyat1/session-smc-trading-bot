#!/usr/bin/env python3
"""
scripts/run_replay.py — Historical Replay for all 5 strategies.

Three-gate process before connecting to Vantage Demo:
  Gate 1 — Smoke test  : every strategy produces signals on every symbol
  Gate 2 — Per-strategy: each demo strategy meets min trades + PF thresholds
  Gate 3 — Portfolio   : combined demo portfolio is net-positive year-by-year

Outputs (written to replay/results/):
  replay_trades_<YYYYMMDD_HHMM>.csv   — full trade log
  replay_report_<YYYYMMDD_HHMM>.md    — human-readable summary + tables
  replay_smoke_<YYYYMMDD_HHMM>.txt    — signal count smoke test

Usage:
  # Full replay, default symbols (EURUSD + GBPUSD), last 3 years
  python3 scripts/run_replay.py

  # Custom date range
  python3 scripts/run_replay.py --start 2022-01-01 --end 2024-12-31

  # Single symbol quick test
  python3 scripts/run_replay.py --symbols EURUSD --start 2024-01-01

  # Include USDJPY (LondonBreakout + NYMomentum only)
  python3 scripts/run_replay.py --symbols EURUSD GBPUSD USDJPY

  # Single strategy (for debugging)
  python3 scripts/run_replay.py --strategies ST-A2

  # Smoke test only (fast — just check signal counts, no metrics)
  python3 scripts/run_replay.py --smoke-only

Prerequisites:
  python3 scripts/fetch_data.py   ← run this first to download data
  (or fetch USDJPY too if needed)
  python3 scripts/fetch_data.py --symbols USDJPY

Before running:
  pip install aiohttp   (for fetch_data.py)
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

from replay.engine import ReplayEngine, ReplayConfig  # noqa: E402
from replay.metrics import gate_check, print_summary  # noqa: E402
from replay.exporter import export_csv, export_report, export_smoke_test  # noqa: E402

# Default date range — 3 years back from today
_DEFAULT_END = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
_DEFAULT_START = (datetime.now(timezone.utc) - timedelta(days=365 * 3)).strftime(
    "%Y-%m-%d"
)

_ALL_STRATEGIES = [
    "ST-A2",
    "LondonBreakout",
    "NYMomentum",
    "AdaptiveSMC",
    "VWAPBreakout",
]
_DEFAULT_SYMBOLS = ["EURUSD", "GBPUSD"]

# ── Preflight check ───────────────────────────────────────────────────────────


def preflight(symbols: list[str], data_dir: Path) -> bool:
    """Check that required data files exist before running the full replay."""
    ok = True
    print("\n[Preflight] Checking data files ...")
    for sym in symbols:
        sym_key = sym[:3] + "_" + sym[3:]
        m15_path = data_dir / f"{sym_key}_M15.csv"
        h4_path = data_dir / f"{sym_key}_H4.csv"

        if not m15_path.exists():
            print(f"  ❌ Missing: {m15_path.name}")
            print(f"     Fix: python3 scripts/fetch_data.py --symbols {sym}")
            ok = False
        else:
            # Quick size check
            size_mb = m15_path.stat().st_size / 1_048_576
            print(f"  ✅ {m15_path.name:<30} ({size_mb:.1f} MB)")

        if not h4_path.exists():
            if sym in ("EURUSD", "GBPUSD"):
                print(f"  ❌ Missing: {h4_path.name}  (needed for ST-A2 + AdaptiveSMC)")
                ok = False
            else:
                print(f"  ⚠  Missing: {h4_path.name}  (H4 bias skipped for {sym})")
        else:
            size_mb = h4_path.stat().st_size / 1_048_576
            print(f"  ✅ {h4_path.name:<30} ({size_mb:.1f} MB)")

    if not ok:
        print("\n  Run fetch_data.py first, then re-run this script.\n")
    return ok


# ── Main ──────────────────────────────────────────────────────────────────────


def main() -> None:
    p = argparse.ArgumentParser(
        description="Historical replay for all 5 strategies",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python3 scripts/run_replay.py\n"
            "  python3 scripts/run_replay.py --start 2022-01-01 --end 2024-12-31\n"
            "  python3 scripts/run_replay.py --symbols EURUSD --smoke-only\n"
        ),
    )
    p.add_argument(
        "--symbols",
        nargs="+",
        default=_DEFAULT_SYMBOLS,
        help=f"Symbols to replay. Default: {_DEFAULT_SYMBOLS}",
    )
    p.add_argument(
        "--start",
        default=_DEFAULT_START,
        help=f"Start date YYYY-MM-DD. Default: {_DEFAULT_START}",
    )
    p.add_argument(
        "--end",
        default=_DEFAULT_END,
        help=f"End date YYYY-MM-DD. Default: {_DEFAULT_END}",
    )
    p.add_argument(
        "--strategies",
        nargs="+",
        default=_ALL_STRATEGIES,
        choices=_ALL_STRATEGIES,
        metavar="NAME",
        help="Strategies to include. Default: all 5",
    )
    p.add_argument(
        "--smoke-only",
        action="store_true",
        help="Run smoke test only (signal counts, no full metrics)",
    )
    p.add_argument(
        "--no-preflight", action="store_true", help="Skip data file existence check"
    )
    p.add_argument("--data-dir", default=None, help="Override data directory path")

    args = p.parse_args()

    data_dir = Path(args.data_dir) if args.data_dir else (_ROOT / "data" / "historical")

    print(f"\n{'='*60}")
    print("  Historical Replay — Pre-Demo Validation")
    print(f"  Period   : {args.start} → {args.end}")
    print(f"  Symbols  : {args.symbols}")
    print(f"  Strategies: {args.strategies}")
    print(f"  Data dir : {data_dir}")
    print(f"{'='*60}")

    # ── Gate 0: Data preflight ────────────────────────────────────────────────
    if not args.no_preflight:
        if not preflight(args.symbols, data_dir):
            sys.exit(1)
        print()

    # ── Build config and run engine ───────────────────────────────────────────
    cfg = ReplayConfig(
        symbols=args.symbols,
        start=args.start,
        end=args.end,
        data_dir=data_dir,
        strategies=args.strategies,
    )

    engine = ReplayEngine(cfg)
    result = engine.run()

    # ── Gate 1: Smoke test ────────────────────────────────────────────────────
    print("\n[Gate 1] Smoke test — checking signal counts ...")
    smoke_path = export_smoke_test(result)

    # Print smoke test to console too
    print()
    print(smoke_path.read_text())

    # Check for zero-signal strategies
    strat_sym_counts: dict[tuple, int] = {}
    for t in result.trades:
        key = (t.strategy, t.symbol)
        strat_sym_counts[key] = strat_sym_counts.get(key, 0) + 1

    zero_signals = []
    for strat in args.strategies:
        for sym in args.symbols:
            count = strat_sym_counts.get((strat, sym), 0)
            if count == 0:
                zero_signals.append(f"{strat}/{sym}")

    if zero_signals:
        print(f"❌ Gate 1 FAIL — Zero signals: {zero_signals}")
        print("   Fix adapter imports and re-run before proceeding.\n")
        # Still export what we have for debugging
        if result.trades:
            export_csv(result)
        sys.exit(1)
    else:
        print("✅ Gate 1 PASS — All strategies produced signals\n")

    if args.smoke_only:
        print("--smoke-only flag set. Stopping after Gate 1.\n")
        return

    # ── Gate 2 + 3: Per-strategy and portfolio gate ───────────────────────────
    print("[Gate 2+3] Evaluating strategy and portfolio gates ...")
    gate = gate_check(result.trades)
    print_summary(result.trades, gate)

    # ── Export outputs ────────────────────────────────────────────────────────
    print("[Exporting results ...]")
    csv_path = export_csv(result)
    report_path = export_report(result, gate)

    # ── Final verdict ─────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print("  OUTPUT FILES")
    print(f"  Trades  : {csv_path.relative_to(_ROOT)}")
    print(f"  Report  : {report_path.relative_to(_ROOT)}")
    print(f"  Smoke   : {smoke_path.relative_to(_ROOT)}")
    print(f"{'='*60}")

    if result.errors:
        print(f"\n  ⚠  {len(result.errors)} errors during replay:")
        for e in result.errors[:10]:
            print(f"     {e}")
        if len(result.errors) > 10:
            print(f"     ... and {len(result.errors) - 10} more (see report)")

    print()
    if gate.demo_ready:
        print("  ✅ REPLAY COMPLETE — All demo gates passed")
        print("  Next step: connect to Vantage Demo (MetaAPI)")
        print("             python3 scripts/run_st_a2_demo.py")
    else:
        failed = [
            g.strategy for g in gate.strategies if g.mode == "demo" and not g.overall
        ]
        print(f"  ❌ REPLAY GATE FAIL — {', '.join(failed)}")
        print(f"     Review: {report_path.relative_to(_ROOT)}")
        print("     Do NOT connect to Vantage Demo until all demo strategies pass.")
    print()


if __name__ == "__main__":
    main()
