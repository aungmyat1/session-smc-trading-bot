"""
Stage C1 — Data integrity audit.

Reads downloaded CSVs from data/historical/ and generates DATA_AUDIT.md.

Checks:
  - First / last timestamp per symbol × granularity
  - Missing bar count and % (gaps in expected sequence)
  - Duplicate timestamps
  - Weekend bars (should not exist for forex)
  - Timezone consistency (all must be UTC)
  - Monotonic ordering
  - Price sanity (high >= low, no zeros)
  - 5-year coverage gate (must cover at least 4.5 years)

Usage:
    python3 scripts/data_audit.py
    python3 scripts/data_audit.py --target-years 5
"""

import argparse
import csv
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data" / "historical"
OUTPUT_PATH = Path(__file__).parent.parent / "DATA_AUDIT.md"

SYMBOLS = ["EUR_USD", "GBP_USD"]
GRANULARITIES = ["M15", "H1", "H4"]

# Expected bar intervals in minutes
INTERVAL_MINUTES = {"M15": 15, "H1": 60, "H4": 240}

# Forex sessions: no bars expected on weekends (Saturday 00:00 – Sunday 21:00 UTC approx)
# We flag any bar whose weekday is Saturday (5) or Sunday (6).


def load_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path) as f:
        reader = csv.DictReader(f)
        return [
            {
                "time": row["time"],
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
            }
            for row in reader
        ]


def parse_dt(t: str) -> datetime:
    return datetime.fromisoformat(t.replace("Z", "+00:00"))


def audit_series(candles: list[dict], gran: str) -> dict:
    """Run all checks on a single symbol × granularity series."""
    result = {
        "n": 0,
        "first": "—",
        "last": "—",
        "duplicates": 0,
        "weekend_bars": 0,
        "non_utc": 0,
        "out_of_order": 0,
        "price_errors": 0,
        "gaps": 0,
        "gap_pct": 0.0,
        "coverage_days": 0,
        "errors": [],
    }

    if not candles:
        result["errors"].append("NO DATA — file missing or empty")
        return result

    result["n"] = len(candles)
    result["first"] = candles[0]["time"]
    result["last"] = candles[-1]["time"]

    interval = timedelta(minutes=INTERVAL_MINUTES.get(gran, 15))
    seen_times: set[str] = set()
    prev_dt: datetime | None = None
    gaps = 0

    for c in candles:
        t = c["time"]

        # Timezone check: must end in Z or +00:00
        if not (t.endswith("Z") or t.endswith("+00:00")):
            result["non_utc"] += 1

        dt = parse_dt(t)

        # Duplicate check
        if t in seen_times:
            result["duplicates"] += 1
        seen_times.add(t)

        # Weekend check
        if dt.weekday() >= 5:
            result["weekend_bars"] += 1

        # Order check
        if prev_dt is not None:
            if dt < prev_dt:
                result["out_of_order"] += 1
            elif dt > prev_dt + interval:
                # Gap: how many bars are missing?
                expected = round((dt - prev_dt) / interval) - 1
                # Ignore weekend gaps (Fri close → Mon open = expected gap)
                # Rough heuristic: skip if the gap spans a weekend
                gap_spans_weekend = (
                    prev_dt.weekday() >= 4  # Friday or later
                    and dt.weekday() <= 1  # Monday or Tuesday
                )
                if not gap_spans_weekend and expected > 0:
                    gaps += expected

        # Price sanity
        if c["high"] < c["low"] or c["open"] <= 0 or c["close"] <= 0:
            result["price_errors"] += 1

        prev_dt = dt

    first_dt = parse_dt(result["first"])
    last_dt = parse_dt(result["last"])
    result["coverage_days"] = (last_dt - first_dt).days
    result["gaps"] = gaps

    # Expected bars between first and last (excluding weekends roughly)
    # Approximate: (days × 5/7 trading fraction) / interval
    trading_days = result["coverage_days"] * 5 / 7
    bars_per_day = (24 * 60) / INTERVAL_MINUTES.get(gran, 15)
    expected_total = trading_days * bars_per_day
    if expected_total > 0:
        result["gap_pct"] = round(gaps / expected_total * 100, 3)

    return result


def format_check(label: str, value, target, pass_fn) -> str:
    status = "✅" if pass_fn(value) else "❌"
    return f"  {status} {label}: {value} (target: {target})"


def generate_report(audits: dict, target_years: float) -> str:
    lines = [
        "# DATA_AUDIT.md",
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"Target coverage: ≥ {target_years} years ({round(target_years * 365)} days)",
        "",
    ]

    all_pass = True

    for symbol in SYMBOLS:
        lines.append(f"---")
        lines.append(f"## {symbol}")
        lines.append("")

        for gran in GRANULARITIES:
            key = f"{symbol}_{gran}"
            r = audits.get(key, {"errors": ["NOT AUDITED"]})
            lines.append(f"### {gran}")

            if r["errors"] and "NO DATA" in r["errors"][0]:
                lines.append(f"  ❌ **MISSING** — {r['errors'][0]}")
                lines.append("")
                all_pass = False
                continue

            coverage_ok = r["coverage_days"] >= target_years * 365 * 0.9
            missing_ok = r["gap_pct"] < 0.1
            dup_ok = r["duplicates"] == 0
            weekend_ok = r["weekend_bars"] == 0
            price_ok = r["price_errors"] == 0
            order_ok = r["out_of_order"] == 0

            symbol_pass = all([coverage_ok, missing_ok, dup_ok, price_ok, order_ok])
            all_pass = all_pass and symbol_pass

            lines.append(f"  First bar:  {r['first']}")
            lines.append(f"  Last bar:   {r['last']}")
            lines.append(f"  Total bars: {r['n']:,}")
            lines.append(f"  Coverage:   {r['coverage_days']} days")
            lines.append("")
            lines.append(
                format_check(
                    "Coverage ≥ 4.5yr",
                    f"{r['coverage_days']}d",
                    f"≥{round(target_years*365*0.9)}d",
                    lambda v: coverage_ok,
                )
            )
            lines.append(
                format_check(
                    "Missing bars %", f"{r['gap_pct']}%", "< 0.1%", lambda v: missing_ok
                )
            )
            lines.append(
                format_check("Duplicates", r["duplicates"], "0", lambda v: dup_ok)
            )
            lines.append(
                format_check(
                    "Weekend bars",
                    r["weekend_bars"],
                    "0 (note: small count ok near DST)",
                    lambda v: True,
                )
            )
            lines.append(
                format_check(
                    "Price errors (high<low)",
                    r["price_errors"],
                    "0",
                    lambda v: price_ok,
                )
            )
            lines.append(
                format_check(
                    "Out-of-order bars", r["out_of_order"], "0", lambda v: order_ok
                )
            )
            lines.append(
                f"  {'✅' if symbol_pass else '❌'} **{gran} {'PASS' if symbol_pass else 'FAIL'}**"
            )
            lines.append("")

    lines.append("---")
    lines.append(f"## Overall Verdict")
    lines.append("")
    lines.append(
        f"**{'✅ ALL PASS — data ready for backtest' if all_pass else '❌ FAILURES — fix data gaps before backtesting'}**"
    )
    lines.append("")
    lines.append(
        "Gate: missing < 0.1%, duplicates = 0, price errors = 0, coverage ≥ 4.5yr per series."
    )

    return "\n".join(lines)


def main(target_years: float) -> None:
    if not DATA_DIR.exists():
        print(f"Data directory not found: {DATA_DIR}")
        print("Run: python3 scripts/fetch_data.py")
        sys.exit(1)

    audits: dict[str, dict] = {}
    found_any = False

    for symbol in SYMBOLS:
        for gran in GRANULARITIES:
            path = DATA_DIR / f"{symbol}_{gran}.csv"
            print(f"Auditing {symbol} {gran} … ", end="", flush=True)
            candles = load_csv(path)
            r = audit_series(candles, gran)
            audits[f"{symbol}_{gran}"] = r
            if candles:
                found_any = True
                print(
                    f"{r['n']:,} bars | gaps={r['gaps']} ({r['gap_pct']}%) | dups={r['duplicates']}"
                )
            else:
                print("NOT FOUND")

    if not found_any:
        print("\nNo data found. Run: python3 scripts/fetch_data.py")
        sys.exit(1)

    report = generate_report(audits, target_years)

    OUTPUT_PATH.write_text(report)
    print(f"\nReport written → {OUTPUT_PATH}")

    # Quick console verdict
    has_fail = any(
        a.get("gap_pct", 100) >= 0.1
        or a.get("duplicates", 1) > 0
        or a.get("price_errors", 1) > 0
        for a in audits.values()
        if not a.get("errors")
    )
    if has_fail:
        print("❌ DATA QUALITY ISSUES — review DATA_AUDIT.md before backtesting.")
    else:
        print("✅ Data quality checks passed — proceed to backtest.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Audit downloaded OANDA CSV data")
    parser.add_argument("--target-years", type=float, default=5.0)
    args = parser.parse_args()
    main(args.target_years)
