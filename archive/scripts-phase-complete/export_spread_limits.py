#!/usr/bin/env python3
"""
E6 — Step 3: Export spread limits and update costs.json.

Reads  : research/cost_model.json
Outputs: research/recommended_spread_limits.yaml
         config/costs.json  (profiles.vantage_measured filled + active_profile set)

Methodology:
  standard = P95 of combined killzone (london + new_york), rounded UP
              to the next 0.05 pip increment.
  stress2x  = standard × 2.

The ceil-to-0.05 ensures modeled cost slightly exceeds the P95 observed
tail — a built-in safety margin without any magic multiplier.

Run after build_cost_model.py.
"""

import json
import math
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_MODEL = _ROOT / "research" / "cost_model.json"
_YAML_OUT = _ROOT / "research" / "recommended_spread_limits.yaml"
_COSTS_JSON = _ROOT / "config" / "costs.json"

STRATEGY_SYMBOLS = ["EURUSD", "GBPUSD"]
CEIL_INCREMENT = 0.05  # round P95 up to next 0.05 pip


def _ceil_to(value, increment):
    return math.ceil(round(value / increment, 8)) * increment


def main():
    if not _MODEL.exists():
        print(f"[ERROR] {_MODEL} not found. Run build_cost_model.py first.")
        raise SystemExit(1)

    model = json.loads(_MODEL.read_text(encoding="utf-8"))
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    recommendations = {}
    for sym in STRATEGY_SYMBOLS:
        sym_data = model["symbols"].get(sym)
        if sym_data is None:
            print(f"[WARN] {sym} not found in cost_model.json — skipping")
            continue
        kz = sym_data.get("combined_killzone", {})
        if not kz or kz.get("p95") is None:
            print(f"[WARN] {sym}: no killzone P95 — skipping")
            continue

        standard = round(_ceil_to(kz["p95"], CEIL_INCREMENT), 4)
        stress2x = round(standard * 2, 4)

        recommendations[sym] = {
            "killzone_n": kz["n"],
            "killzone_avg": kz["avg"],
            "killzone_median": kz["median"],
            "killzone_p95": kz["p95"],
            "standard": standard,
            "stress2x": stress2x,
        }

    if not recommendations:
        print("[ERROR] No symbols could be processed. Check cost_model.json.")
        raise SystemExit(1)

    # Write YAML
    lines = [
        "# recommended_spread_limits.yaml",
        f"# Generated:   {now_str}",
        f"# Source:      {_MODEL.relative_to(_ROOT)}",
        f"# Data rows:   {model['row_count']:,}",
        "# Methodology: P95 of combined killzone (london + new_york),",
        "#              rounded UP to next 0.05 pip. stress2x = standard × 2.",
        "",
        f"active_profile: vantage_measured",
        f"generated_at:   {now_str}",
        "",
        "symbols:",
    ]
    for sym, d in recommendations.items():
        lines += [
            f"  {sym}:",
            f"    killzone_n:       {d['killzone_n']}",
            f"    killzone_avg:     {d['killzone_avg']:.4f}  pip",
            f"    killzone_median:  {d['killzone_median']:.4f}  pip",
            f"    killzone_p95:     {d['killzone_p95']:.4f}  pip",
            f"    standard:         {d['standard']:.4f}  pip  # P95 ceil-0.05 — inject into backtest",
            f"    stress2x:         {d['stress2x']:.4f}  pip  # standard × 2",
            "",
        ]

    _YAML_OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"[+] Written: {_YAML_OUT.relative_to(_ROOT)}")

    # Update costs.json
    costs = json.loads(_COSTS_JSON.read_text(encoding="utf-8"))
    for sym, d in recommendations.items():
        costs["profiles"]["vantage_measured"][sym] = {
            "standard": d["standard"],
            "stress2x": d["stress2x"],
        }
        if "_note" in costs["profiles"]["vantage_measured"]:
            costs["profiles"]["vantage_measured"]["_note"] = (
                f"Measured from research/spread_samples.csv via E6 pipeline. "
                f"Generated: {now_str}."
            )
    costs["active_profile"] = "vantage_measured"

    _COSTS_JSON.write_text(json.dumps(costs, indent=2), encoding="utf-8")
    print(f"[+] Updated:  {_COSTS_JSON.relative_to(_ROOT)}")
    print(f"    active_profile → vantage_measured")

    # Print summary
    print(
        f"\n{'Symbol':<10} {'KZ_avg':>8} {'KZ_p95':>8} {'standard':>10} {'stress2x':>10}"
    )
    print("-" * 52)
    for sym, d in recommendations.items():
        placeholder = {"EURUSD": 1.4, "GBPUSD": 1.8}.get(sym, "?")
        delta = d["standard"] - placeholder
        delta_str = f"{delta:+.4f}"
        print(
            f"{sym:<10} {d['killzone_avg']:>8.4f} {d['killzone_p95']:>8.4f} "
            f"{d['standard']:>10.4f} {d['stress2x']:>10.4f}  (vs placeholder {placeholder}: {delta_str})"
        )

    print(
        "\nNext: python3 scripts/backtest_session_liquidity.py "
        "--costs-json config/costs.json"
    )


if __name__ == "__main__":
    main()
