#!/usr/bin/env python3
"""Build a spread cost model from `research/spread_samples.csv`."""

from __future__ import annotations

import csv
import json
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
SRC = _ROOT / "research" / "spread_samples.csv"
OUT = _ROOT / "research" / "cost_model.json"

KILLZONE_SESSIONS = {"london", "new_york"}


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(_ROOT))
    except ValueError:
        return str(path)


def percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    idx = (len(ordered) - 1) * p / 100
    lo = int(idx)
    hi = min(lo + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (idx - lo)


def stats(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {
            "n": 0,
            "avg": None,
            "median": None,
            "p90": None,
            "p95": None,
            "p99": None,
            "min": None,
            "max": None,
        }
    return {
        "n": len(values),
        "avg": round(statistics.mean(values), 4),
        "median": round(statistics.median(values), 4),
        "p90": round(percentile(values, 90) or 0.0, 4),
        "p95": round(percentile(values, 95) or 0.0, 4),
        "p99": round(percentile(values, 99) or 0.0, 4),
        "min": round(min(values), 4),
        "max": round(max(values), 4),
    }


def build_model(rows: list[dict[str, str]]) -> dict[str, object]:
    buckets: dict[tuple[str, str], list[float]] = defaultdict(list)
    total_rows = 0
    skipped = 0
    for row in rows:
        total_rows += 1
        symbol = row.get("symbol", "").strip()
        session = row.get("session", "").strip()
        try:
            spread = float(row.get("spread_pips", ""))
        except (TypeError, ValueError):
            skipped += 1
            continue
        if not symbol or not session:
            skipped += 1
            continue
        buckets[(symbol, session)].append(spread)

    symbols = sorted({sym for sym, _ in buckets})
    sessions = sorted({session for _, session in buckets})

    model: dict[str, object] = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": display_path(SRC),
        "row_count": total_rows,
        "skipped_rows": skipped,
        "symbols": {},
    }

    symbols_payload: dict[str, object] = {}
    for sym in symbols:
        sym_payload: dict[str, object] = {}
        combined: list[float] = []
        for session in sessions:
            values = buckets.get((sym, session), [])
            sym_payload[session] = stats(values)
            if session in KILLZONE_SESSIONS:
                combined.extend(values)
        sym_payload["combined_killzone"] = stats(combined)
        symbols_payload[sym] = sym_payload

    model["symbols"] = symbols_payload
    return model


def main() -> int:
    if not SRC.exists():
        print(f"[ERROR] {SRC} not found. Run scripts/capture_spreads.py first.")
        return 1

    with SRC.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    model = build_model(rows)
    OUT.write_text(json.dumps(model, indent=2), encoding="utf-8")
    print(f"[+] Written: {display_path(OUT)}")
    print(f"Total rows: {model['row_count']:,}  |  Skipped: {model['skipped_rows']}")
    print("Next: python3 scripts/export_spread_limits.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
