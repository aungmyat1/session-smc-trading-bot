#!/usr/bin/env python3
"""
Phase 2 Dataset Freeze — creates an immutable snapshot of all E6 inputs.

Usage:
    python3 scripts/freeze_phase2_dataset.py

Inputs  (must all exist before running):
    research/spread_samples.csv   — raw spread samples from capture_spreads.py
    research/cost_model.json      — computed by build_cost_model.py
    config/costs.json             — active cost profile config

Output:
    research/e6_dataset_snapshot/
        spread_samples.csv          — verbatim copy
        cost_model.json             — verbatim copy
        costs.json                  — verbatim copy
        dataset_manifest.json       — SHA256 hashes + coverage + gate status

Purpose:
    Guarantees that the E6 result is reproducible:
        E6 result = exact dataset + exact cost model + exact configuration
    After freezing, costs.json will be modified by export_spread_limits.py and
    the backtest will be re-run with measured costs. The snapshot preserves
    the pre-E6 state of every input for audit and replay.

When to run:
    ONLY after check_phase2_completion.py exits 0. Running on partial data
    produces a snapshot that cannot be used for a valid E6 run.
    The script warns but does not block — gate status is recorded in the manifest.
"""

import csv
import hashlib
import json
import shutil
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_SNAP = _ROOT / "research" / "e6_dataset_snapshot"

SOURCES = {
    "spread_samples.csv": _ROOT / "research" / "spread_samples.csv",
    "cost_model.json":    _ROOT / "research" / "cost_model.json",
    "costs.json":         _ROOT / "config" / "costs.json",
}

KILLZONE_SESSIONS = {"london", "new_york"}


# ── Utilities ─────────────────────────────────────────────────────────────────

def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _gate_status():
    """Run check_phase2_completion.py and return (exit_code, summary_text)."""
    r = subprocess.run(
        [sys.executable, str(_ROOT / "scripts" / "check_phase2_completion.py")],
        capture_output=True, text=True,
    )
    output = (r.stdout + r.stderr).strip()
    return r.returncode, output


def _scan_samples(path: Path):
    """
    Parse spread_samples.csv and return a coverage dict.

    Returns:
        total_rows, symbols, session_info, earliest, latest
        session_info: { session: { "dates": sorted list, "count": int } }
    """
    symbols      = set()
    session_rows = defaultdict(list)          # session → [date_str]
    sym_sess_n   = defaultdict(int)           # (sym, sess) → count
    earliest = latest = None

    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        total = 0
        for row in reader:
            total += 1
            ts   = row.get("time_utc", "")
            sym  = row.get("symbol", "").strip()
            sess = row.get("session", "").strip()
            if sym:
                symbols.add(sym)
            if sess:
                session_rows[sess].append(ts[:10])
                sym_sess_n[(sym, sess)] += 1
            if ts:
                if earliest is None or ts < earliest:
                    earliest = ts
                if latest is None or ts > latest:
                    latest = ts

    session_info = {}
    for sess, dates in session_rows.items():
        unique_dates = sorted(set(d for d in dates if d))
        session_info[sess] = {"dates": unique_dates, "count": len(dates)}

    return total, sorted(symbols), session_info, sym_sess_n, earliest, latest


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    print()
    print("╔══════════════════════════════════════════════════════╗")
    print("║  Phase 2 Dataset Freeze                              ║")
    print("╚══════════════════════════════════════════════════════╝")
    print(f"  Timestamp: {now_str}")
    print()

    # ── Step 1: Verify all source files exist ──────────────────────────────────
    print("[Step 1] Checking source files ...")
    missing = []
    for name, p in SOURCES.items():
        if p.exists():
            print(f"  ✅  {name}  ({p.stat().st_size:,} bytes)")
        else:
            print(f"  ❌  {name}  MISSING — {p}")
            missing.append(name)

    if missing:
        print()
        print("[ABORT] Missing required files:")
        for m in missing:
            if m == "cost_model.json":
                print(f"  • {m} — run: python3 scripts/build_cost_model.py")
            elif m == "spread_samples.csv":
                print(f"  • {m} — spread capture not yet started")
            else:
                print(f"  • {m}")
        raise SystemExit(1)

    # ── Step 2: Gate status (warn only — do not block) ─────────────────────────
    print()
    print("[Step 2] Checking Phase 2 gate ...")
    gate_exit, gate_output = _gate_status()
    gate_met = gate_exit == 0

    if gate_met:
        print(f"  ✅  Gate: READY_FOR_COST_REVALIDATION")
    else:
        print(f"  ⚠️   Gate: NOT YET MET — snapshot recorded as partial")
        print(f"       Run freeze again after gate opens for production use.")
    for line in gate_output.splitlines():
        print(f"       {line}")

    # ── Step 3: Parse spread_samples.csv ──────────────────────────────────────
    print()
    print("[Step 3] Scanning spread_samples.csv ...")
    total, symbols, session_info, sym_sess_n, earliest, latest = _scan_samples(
        SOURCES["spread_samples.csv"]
    )

    kz_sessions = {s: d for s, d in session_info.items() if s in KILLZONE_SESSIONS}
    london_days = len(kz_sessions.get("london", {}).get("dates", []))
    ny_days     = len(kz_sessions.get("new_york", {}).get("dates", []))

    print(f"  Rows:          {total:,}")
    print(f"  Symbols:       {symbols}")
    print(f"  Earliest:      {(earliest or '')[:19]} UTC")
    print(f"  Latest:        {(latest or '')[:19]} UTC")
    print(f"  London days:   {london_days}")
    print(f"  NY days:       {ny_days}")
    for sess, info in sorted(session_info.items()):
        print(f"  {sess:<12}: {info['count']:,} rows  "
              f"({len(info['dates'])} session days)")

    # ── Step 4: Compute SHA256 hashes ─────────────────────────────────────────
    print()
    print("[Step 4] Computing SHA256 hashes ...")
    hashes = {}
    for name, p in SOURCES.items():
        h = _sha256(p)
        hashes[name] = h
        print(f"  {name}")
        print(f"    SHA256: {h}")

    # ── Step 5: Create snapshot directory ─────────────────────────────────────
    print()
    print("[Step 5] Creating snapshot ...")

    if _SNAP.exists():
        existing_manifest = _SNAP / "dataset_manifest.json"
        if existing_manifest.exists():
            prev = json.loads(existing_manifest.read_text())
            print(f"  ⚠️   Overwriting existing snapshot (created {prev.get('created_at', '?')})")
        shutil.rmtree(_SNAP)

    _SNAP.mkdir(parents=True)

    # Copy files verbatim
    for name, src in SOURCES.items():
        dst = _SNAP / name
        shutil.copy2(src, dst)
        print(f"  Copied: {name}  ({dst.stat().st_size:,} bytes)")

    # ── Step 6: Write dataset_manifest.json ───────────────────────────────────
    print()
    print("[Step 6] Writing dataset_manifest.json ...")

    # Per-symbol killzone coverage
    sym_kz_n = {}
    for sym in symbols:
        n = sum(sym_sess_n.get((sym, s), 0) for s in KILLZONE_SESSIONS)
        sym_kz_n[sym] = n

    # Load costs.json for active_profile snapshot
    costs = json.loads(SOURCES["costs.json"].read_text())

    session_manifest = {}
    for sess, info in session_info.items():
        entry = {"samples": info["count"]}
        if info["dates"]:
            entry["dates"] = info["dates"]
            entry["session_count"] = len(info["dates"])
        session_manifest[sess] = entry

    manifest = {
        "created_at":        now_str,
        "freeze_version":    "1",
        "gate_status": {
            "collection_complete": gate_met,
            "exit_code":           gate_exit,
            "summary":             gate_output,
        },
        "source_files": {
            "spread_samples.csv": {
                "sha256":     hashes["spread_samples.csv"],
                "rows":       total,
                "size_bytes": SOURCES["spread_samples.csv"].stat().st_size,
            },
            "cost_model.json": {
                "sha256":     hashes["cost_model.json"],
                "size_bytes": SOURCES["cost_model.json"].stat().st_size,
            },
            "costs.json": {
                "sha256":         hashes["costs.json"],
                "active_profile": costs.get("active_profile"),
                "size_bytes":     SOURCES["costs.json"].stat().st_size,
            },
        },
        "coverage": {
            "symbols":           symbols,
            "total_samples":     total,
            "earliest_timestamp": (earliest or "")[:19] + "Z" if earliest else None,
            "latest_timestamp":   (latest or "")[:19] + "Z" if latest else None,
            "london_sessions":   london_days,
            "ny_sessions":       ny_days,
            "sessions":          session_manifest,
            "killzone_samples_by_symbol": sym_kz_n,
        },
    }

    manifest_path = _SNAP / "dataset_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"  Written: {manifest_path.relative_to(_ROOT)}")

    # ── Step 7: Integrity verification (re-hash copied files) ─────────────────
    print()
    print("[Step 7] Verifying snapshot integrity ...")
    all_ok = True
    for name in SOURCES:
        orig_hash = hashes[name]
        copy_hash = _sha256(_SNAP / name)
        ok = orig_hash == copy_hash
        all_ok = all_ok and ok
        icon = "✅" if ok else "❌"
        print(f"  {icon}  {name}  {'match' if ok else 'MISMATCH — copy failed'}")

    if not all_ok:
        print()
        print("[ABORT] Integrity check failed. Snapshot is corrupt. Remove and retry.")
        raise SystemExit(1)

    # ── Summary ───────────────────────────────────────────────────────────────
    print()
    print("╔══════════════════════════════════════════════════════╗")
    print("║  Snapshot Complete                                   ║")
    print("╚══════════════════════════════════════════════════════╝")
    print(f"  Location:   research/e6_dataset_snapshot/")
    print(f"  Rows:       {total:,}")
    print(f"  Symbols:    {', '.join(symbols)}")
    print(f"  London:     {london_days}/5 sessions")
    print(f"  NY:         {ny_days}/5 sessions")
    print(f"  Gate:       {'✅ READY' if gate_met else '⚠️  NOT YET MET (partial snapshot)'}")
    print()

    if gate_met:
        print("  Next step: bash scripts/run_e6_revalidation.sh")
    else:
        print("  Next step: continue collecting until gate opens, then re-run this script.")
        print("             Gate check: python3 scripts/check_phase2_completion.py")

    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
