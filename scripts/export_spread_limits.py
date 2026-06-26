#!/usr/bin/env python3
"""Export measured spread limits and update `config/costs.json`."""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
MODEL_PATH = _ROOT / "research" / "cost_model.json"
YAML_PATH = _ROOT / "research" / "recommended_spread_limits.yaml"
COSTS_PATH = _ROOT / "config" / "costs.json"

STRATEGY_SYMBOLS = ("EURUSD", "GBPUSD")
CEIL_INCREMENT = 0.05


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(_ROOT))
    except ValueError:
        return str(path)


def ceil_to(value: float, increment: float) -> float:
    return math.ceil(round(value / increment, 8)) * increment


def main() -> int:
    if not MODEL_PATH.exists():
        print(f"[ERROR] {MODEL_PATH} not found. Run scripts/build_cost_model.py first.")
        return 1

    model = json.loads(MODEL_PATH.read_text(encoding="utf-8"))
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    recommendations: dict[str, dict[str, float | int | None]] = {}
    for symbol in STRATEGY_SYMBOLS:
        symbol_data = model.get("symbols", {}).get(symbol)
        if not symbol_data:
            print(f"[WARN] {symbol} missing from cost model — skipping")
            continue
        kz = symbol_data.get("combined_killzone", {})
        if not kz or kz.get("p95") is None:
            print(f"[WARN] {symbol}: no killzone P95 — skipping")
            continue
        standard = round(ceil_to(float(kz["p95"]), CEIL_INCREMENT), 4)
        recommendations[symbol] = {
            "killzone_n": kz["n"],
            "killzone_avg": kz["avg"],
            "killzone_median": kz["median"],
            "killzone_p95": kz["p95"],
            "standard": standard,
            "stress2x": round(standard * 2, 4),
        }

    if not recommendations:
        print("[ERROR] No symbol recommendations produced.")
        return 1

    lines = [
        "# recommended_spread_limits.yaml",
        f"# Generated:   {now_str}",
        f"# Source:      {display_path(MODEL_PATH)}",
        f"# Data rows:    {model['row_count']:,}",
        "# Methodology: combined killzone P95 rounded UP to next 0.05 pip.",
        "",
        "active_profile: vantage_measured",
        f"generated_at:   {now_str}",
        "",
        "symbols:",
    ]
    for symbol, data in recommendations.items():
        lines.extend(
            [
                f"  {symbol}:",
                f"    killzone_n:       {data['killzone_n']}",
                f"    killzone_avg:     {data['killzone_avg']:.4f}  pip",
                f"    killzone_median:  {data['killzone_median']:.4f}  pip",
                f"    killzone_p95:     {data['killzone_p95']:.4f}  pip",
                f"    standard:         {data['standard']:.4f}  pip",
                f"    stress2x:         {data['stress2x']:.4f}  pip",
                "",
            ]
        )

    YAML_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"[+] Written: {display_path(YAML_PATH)}")

    costs = json.loads(COSTS_PATH.read_text(encoding="utf-8"))
    costs.setdefault("profiles", {}).setdefault("vantage_measured", {})
    for symbol, data in recommendations.items():
        costs["profiles"]["vantage_measured"][symbol] = {
            "standard": data["standard"],
            "stress2x": data["stress2x"],
        }
        if "_note" in costs["profiles"]["vantage_measured"]:
            costs["profiles"]["vantage_measured"]["_note"] = (
                f"Measured from research/spread_samples.csv via E6 pipeline. Generated: {now_str}."
            )
    costs["active_profile"] = "vantage_measured"
    COSTS_PATH.write_text(json.dumps(costs, indent=2), encoding="utf-8")
    print(f"[+] Updated:  {display_path(COSTS_PATH)}")
    print("    active_profile → vantage_measured")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
