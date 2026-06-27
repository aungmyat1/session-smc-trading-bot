"""
pipeline/run_phase0.py
Phase-0 Gate Orchestrator — runs the full pipeline end to end.

Steps:
  1. Build feature Parquets (Asian range, session ranges)
  2. Run deterministic replay — standard + 2× spread stress
  3. Write all results to PostgreSQL
  4. Print gate verdict

Usage:
    python -m pipeline.run_phase0 --start 2020-01-01 --end 2025-01-01
    python -m pipeline.run_phase0 --symbol EURUSD --start 2022-01-01 --end 2025-01-01
    python -m pipeline.run_phase0 --skip-db   # dry run, no PostgreSQL needed
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date

import polars as pl

from db.runtime import resolve_database_url
from .config import (
    FEATURES_DIR,
    PHASE0_MIN_NET_PF,
    PHASE0_MIN_TRADES,
    SPREAD_STANDARD,
    SPREAD_STRESS_2X,
    SYMBOLS,
)
from .pipeline_02_build_features import process_symbol as build_symbol_features
from .pipeline_03_replay_engine import evaluate_gate, replay_symbol
from .pipeline_04_write_db import write_all


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase-0 Gate — full pipeline")
    parser.add_argument("--symbol",        choices=SYMBOLS, help="Restrict to one symbol")
    parser.add_argument("--start",         default="2020-01-01")
    parser.add_argument("--end",           default="2025-01-01")
    parser.add_argument("--skip-features", action="store_true",
                        help="Skip feature build (use cached Parquets)")
    parser.add_argument("--skip-db",       action="store_true",
                        help="Skip PostgreSQL write (dry-run / no DB needed)")
    args = parser.parse_args()

    targets = [args.symbol] if args.symbol else SYMBOLS
    start   = date.fromisoformat(args.start)
    end     = date.fromisoformat(args.end)

    print("=" * 60)
    print("Phase-0 Gate  |  ST-A2 Sweep Reversal")
    print(f"Period: {start} → {end}  |  Symbols: {targets}")
    print("=" * 60)

    # ── Step 1: Feature Parquets ──────────────────────────────────────────────
    if not args.skip_features:
        print("\n[1/3] Building feature Parquets...")
        for sym in targets:
            build_symbol_features(sym)

    # ── Step 2: Replay (standard + 2× stress) ────────────────────────────────
    print("\n[2/3] Running deterministic replay (standard + 2× stress)...")

    all_trades: list[dict] = []
    gate_results: list[dict] = []

    for scenario_name, spread_map in [
        ("standard",   SPREAD_STANDARD),
        ("stress_2x",  SPREAD_STRESS_2X),
    ]:
        print(f"\n  Scenario: {scenario_name}")
        for sym in targets:
            run_id = f"ST-A-{sym}-{scenario_name}-{start}-{end}"
            trades = replay_symbol(sym, start, end, spread_map[sym], run_id)
            gate   = evaluate_gate(trades, f"{sym}/{scenario_name}")
            # Tag each trade with run_id (replay_symbol already does this,
            # but scenario may need re-tagging if run_id carries it)
            all_trades.extend(trades)
            gate_results.append(gate)
            mark = "✅" if gate["pass"] else "❌"
            print(
                f"    {mark} {sym}: n={gate['n']}  "
                f"PF={gate['net_pf']}  WR={gate['win_rate']}%  "
                f"avg_R={gate['avg_net_r']}"
            )

    # Cache to Parquet
    if all_trades:
        FEATURES_DIR.mkdir(parents=True, exist_ok=True)
        pl.DataFrame(all_trades).write_parquet(
            FEATURES_DIR / "_replay_results.parquet", compression="zstd"
        )

    # ── Step 3: Write to PostgreSQL ───────────────────────────────────────────
    if not args.skip_db and all_trades:
        print("\n[3/3] Writing to PostgreSQL...")
        from sqlalchemy import create_engine
        db_url = resolve_database_url()
        if not db_url:
            raise SystemExit(
                "DATABASE_URL is required for phase-0 DB writes; set it explicitly or use --skip-db"
            )
        eng = create_engine(db_url, pool_pre_ping=True)
        df = pl.read_parquet(FEATURES_DIR / "_replay_results.parquet")
        write_all(eng, df)
    elif args.skip_db:
        print("\n[3/3] Skipped (--skip-db)")

    # ── Verdict ───────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("PHASE-0 GATE VERDICT")
    print("=" * 60)
    overall_pass = True
    for g in gate_results:
        mark = "✅ PASS" if g["pass"] else "❌ FAIL"
        print(
            f"  {mark}  {g['label']:<28}  "
            f"n={g['n']:<5}  PF={g['net_pf']:<7}  WR={g['win_rate']}%"
        )
        if not g["pass"]:
            overall_pass = False

    print()
    if overall_pass:
        print("✅  ALL SCENARIOS PASS — proceed to Phase-1 paper trading")
        print("   Register PASS in docs/VERDICT_LOG.md before starting Phase-1.")
    else:
        print("❌  GATE FAIL — do NOT proceed to paper trading")
        print("   Register failed trial in docs/VERDICT_LOG.md.")
        print("   Every parameter change = new trial ID. Do not re-run on the same ID.")
        sys.exit(1)


if __name__ == "__main__":
    main()
