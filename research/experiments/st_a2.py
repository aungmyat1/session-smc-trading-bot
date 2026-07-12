from __future__ import annotations

import csv
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, pstdev
from typing import Any, Callable

import yaml

from research.research_validation import git_state, load_trade_ledger, load_yaml, trade_metrics, write_json
from research.st_a2_freeze import STRATEGY_CONFIG, _ledger_hash, canonical_strategy_hash

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "config" / "experiments" / "st_a2_hypothesis_experiments.yaml"
DEFAULT_OUTPUT_DIR = ROOT / "artifacts" / "experiments"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _resolve(path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else ROOT / candidate


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _finite(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except Exception:
        return default
    return number if math.isfinite(number) else default


def _cost(row: dict[str, Any]) -> float:
    return (
        _finite(row.get("spread_cost"))
        + _finite(row.get("commission_cost", row.get("commission")))
        + _finite(row.get("slippage_cost", row.get("slippage")))
    )


def _cost_ratio(row: dict[str, Any]) -> float:
    gross = abs(_finite(row.get("gross_pnl")))
    return _cost(row) / gross if gross else float("inf")


def _pf(values: list[float]) -> float:
    wins = sum(value for value in values if value > 0)
    losses = abs(sum(value for value in values if value < 0))
    if losses == 0:
        return float("inf") if wins > 0 else 0.0
    return wins / losses


def _sharpe(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    sd = pstdev(values)
    return mean(values) / sd * math.sqrt(len(values)) if sd else 0.0


def _max_drawdown(values: list[float]) -> float:
    running = peak = worst = 0.0
    for value in values:
        running += value
        peak = max(peak, running)
        worst = max(worst, peak - running)
    return worst


def _stress_metrics(rows: list[dict[str, Any]], cost_multiplier: float) -> dict[str, Any]:
    values = [_finite(row.get("gross_pnl")) - (_cost(row) * cost_multiplier) for row in rows]
    wins = [value for value in values if value > 0]
    return {
        "trade_count": len(values),
        "net_profit": sum(values),
        "profit_factor": _pf(values),
        "sharpe": _sharpe(values),
        "max_drawdown_r": _max_drawdown(values),
        "expectancy": mean(values) if values else 0.0,
        "win_rate": len(wins) / len(values) if values else 0.0,
    }


def _normalized_baseline_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    standard = trade_metrics(rows)
    stress = _stress_metrics(rows, 2.0)
    return {
        "trade_count": int(standard["trade_count"]),
        "pf_standard": standard["profit_factor_after_cost"],
        "pf_2x": stress["profit_factor"],
        "sharpe_standard": standard["sharpe"],
        "sharpe_2x": stress["sharpe"],
        "drawdown_r_standard": standard["max_drawdown_r"],
        "drawdown_r_2x": stress["max_drawdown_r"],
        "expectancy_standard": standard["expectancy"],
        "expectancy_2x": stress["expectancy"],
        "win_rate_standard": standard["win_rate"],
        "net_profit_standard": standard["net_profit"],
        "net_profit_2x": stress["net_profit"],
    }


def _worst_symbol() -> str:
    payload = _load_json(ROOT / "artifacts" / "ST-A2_symbol_attribution.json")
    return str(payload.get("rankings", {}).get("worst_symbol") or "XAUUSD")


def _worst_regime() -> str:
    payload = _load_json(ROOT / "artifacts" / "ST-A2_regime_attribution.json")
    destructive = payload.get("destructive_regimes") or []
    regimes = payload.get("regimes") or {}
    if destructive:
        return min(destructive, key=lambda name: _finite(regimes.get(name, {}).get("edge_score")))
    return "RANGE_LOW_VOL"


def _quality_score(row: dict[str, Any], components: dict[str, int]) -> int:
    score = 0
    if str(row.get("symbol")) == "GBPUSD":
        score += int(components.get("gbpusd", 0))
    if str(row.get("session")).lower() == "new_york":
        score += int(components.get("new_york", 0))
    if str(row.get("market_regime")) != "RANGE_LOW_VOL":
        score += int(components.get("non_range_low_vol", 0))
    if _cost_ratio(row) <= 0.15:
        score += int(components.get("cost_ratio_lte_0_15", 0))
    if str(row.get("smc_context") or "[]") not in {"", "[]"}:
        score += int(components.get("smc_context_present", 0))
    return score


def _filter_for(rule: dict[str, Any]) -> tuple[Callable[[dict[str, Any]], bool], dict[str, Any]]:
    kind = str(rule.get("type"))
    if kind == "max_cost_ratio":
        threshold = float(rule["max_cost_to_gross_abs"])
        return lambda row: _cost_ratio(row) <= threshold, {"max_cost_to_gross_abs": threshold}
    if kind == "exclude_worst_symbol":
        symbol = _worst_symbol() or str(rule.get("fallback_symbol", "XAUUSD"))
        return lambda row: str(row.get("symbol")) != symbol, {"excluded_symbol": symbol}
    if kind == "exclude_session":
        session = str(rule["session"]).lower()
        return lambda row: str(row.get("session")).lower() != session, {"excluded_session": session}
    if kind == "exclude_worst_regime":
        regime = _worst_regime() or str(rule.get("fallback_regime", "RANGE_LOW_VOL"))
        return lambda row: str(row.get("market_regime")) != regime, {"excluded_regime": regime}
    if kind == "minimum_quality_score":
        min_score = int(rule["min_score"])
        components = dict(rule.get("components") or {})
        return lambda row: _quality_score(row, components) >= min_score, {"min_score": min_score, "components": components}
    raise ValueError(f"Unsupported experiment rule type: {kind}")


def _robustness_score(rows: list[dict[str, Any]]) -> float:
    if not rows:
        return 0.0
    months = sorted({str(row.get("entry_time") or "")[:7] for row in rows if str(row.get("entry_time") or "")[:7]})
    symbols = {str(row.get("symbol")) for row in rows}
    regimes = {str(row.get("market_regime")) for row in rows}
    month_score = min(1.0, len(months) / 18.0)
    symbol_score = min(1.0, len(symbols) / 3.0)
    regime_score = min(1.0, len(regimes) / 4.0)
    count_score = min(1.0, len(rows) / 200.0)
    return round((month_score * 0.35) + (symbol_score * 0.25) + (regime_score * 0.20) + (count_score * 0.20), 6)


def _classification(delta: dict[str, float], retained: float, trade_count: int) -> str:
    if trade_count < 50:
        return "REQUIRES_ADDITIONAL_DATA"
    if delta["pf_2x"] > 0 and delta["sharpe"] > 0 and delta["drawdown_r"] > 0 and retained >= 0.50:
        return "VALIDATED"
    if delta["pf_2x"] <= 0 and delta["sharpe"] <= 0:
        return "REJECTED"
    return "REQUIRES_ADDITIONAL_DATA"


def _gate_status(metrics: dict[str, Any]) -> str:
    passed = (
        int(metrics["trade_count"]) > 200
        and _finite(metrics["pf_2x"]) > 1.25
        and _finite(metrics["sharpe_2x"]) > 1.20
        and _finite(metrics["drawdown_r_2x"]) < 15.0
        and _finite(metrics["expectancy_2x"]) > 0.0
    )
    return "PASS" if passed else "FAIL"


def _ranking_score(
    delta: dict[str, float],
    retained: float,
    robustness_delta: float,
    weights: dict[str, float],
) -> float:
    pf_score = max(-1.0, min(1.0, delta["pf_2x"]))
    sharpe_score = max(-1.0, min(1.0, delta["sharpe"]))
    dd_score = max(-1.0, min(1.0, delta["drawdown_r"] / 10.0))
    retention_score = max(0.0, min(1.0, retained))
    robust_score = max(-1.0, min(1.0, robustness_delta))
    return round(
        pf_score * float(weights.get("pf_2x_improvement", 0.35))
        + sharpe_score * float(weights.get("sharpe_improvement", 0.25))
        + dd_score * float(weights.get("drawdown_reduction", 0.20))
        + retention_score * float(weights.get("trade_count_retention", 0.10))
        + robust_score * float(weights.get("robustness", 0.10)),
        6,
    )


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _report(results: list[dict[str, Any]], output_path: Path, baseline: dict[str, Any], manifest: dict[str, Any]) -> None:
    lines = [
        "# ST-A2 Hypothesis-Driven Experiment Recommendation",
        "",
        f"Generated: {manifest['created_at']}",
        "",
        "## Baseline",
        "",
        f"- Ledger hash: `{manifest['baseline']['ledger_hash']}`",
        f"- Trades: {baseline['trade_count']}",
        f"- PF 2x: {baseline['pf_2x']:.4f}",
        f"- Sharpe 2x: {baseline['sharpe_2x']:.4f}",
        f"- Max drawdown 2x: {baseline['drawdown_r_2x']:.4f}R",
        "",
        "## Recommendation",
        "",
    ]
    valid = [row for row in results if row["classification"] == "VALIDATED"]
    if valid:
        best = valid[0]
        lines.append(f"Strongest baseline-relative improvement: **{best['experiment_id']} {best['name']}**.")
    else:
        lines.append("No single fixed hypothesis is ready for promotion. Treat all improvements as exploratory until more trades are available.")
    lines += [
        "",
        "Classification is relative to ST-A2_v1 baseline. Current SVOS gate status is reported separately.",
        "No parameter sweep or combined optimization was performed because the frozen baseline has fewer than 500 trades.",
        "",
        "## Experiment Verdicts",
        "",
        "| Rank | Experiment | Classification | Gate | Trades | PF 2x | Sharpe 2x | DD 2x | Retention | Score |",
        "|---|---|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in results:
        lines.append(
            f"| {row['rank']} | {row['experiment_id']} {row['name']} | {row['classification']} | {row['current_gate_status']} | "
            f"{row['trade_count']} | {row['pf_2x']:.4f} | {row['sharpe_2x']:.4f} | "
            f"{row['drawdown_r_2x']:.4f}R | {row['trade_count_retention']:.2%} | {row['ranking_score']:.4f} |"
        )
    if not any(row["current_gate_status"] == "PASS" for row in results):
        lines += [
            "",
            "No experiment passes the current Phase-3 gate in isolation; the best candidates are hypothesis evidence for Robustness Validation planning, not approval evidence.",
        ]
    lines += [
        "",
        "## Governance",
        "",
        "- ST-A2_v1 baseline config and frozen ledgers were not modified.",
        "- Experiments are post-ledger, single-hypothesis filters only.",
        "- Results are not Production Approval evidence and require Robustness Validation before progression.",
        "",
    ]
    output_path.write_text("\n".join(lines), encoding="utf-8")


def run_st_a2_experiments(config_path: Path = DEFAULT_CONFIG, output_dir: Path = DEFAULT_OUTPUT_DIR) -> dict[str, Any]:
    config = load_yaml(config_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    ledger_dir = _resolve(config["baseline_ledger_dir"])
    ledger_rows = load_trade_ledger(ledger_dir)
    baseline_manifest = _load_json(_resolve(config["baseline_manifest"]))
    baseline_hash = _ledger_hash(ledger_rows)
    if baseline_manifest and baseline_manifest.get("ledger_hash") != baseline_hash:
        raise RuntimeError("Frozen ST-A2 ledger hash mismatch; refusing to run experiments.")

    baseline_metrics = _normalized_baseline_metrics(ledger_rows)
    baseline_robustness = _robustness_score(ledger_rows)
    baseline_strategy_hash = canonical_strategy_hash(STRATEGY_CONFIG)
    manifest = {
        "experiment_set_id": config["experiment_set_id"],
        "created_at": _now(),
        "git": git_state(),
        "constraints": config["constraints"],
        "baseline": {
            "strategy_id": config["strategy_id"],
            "version": str(config["baseline_version"]),
            "config_path": config["baseline_config"],
            "config_sha256": _sha256(_resolve(config["baseline_config"])),
            "strategy_hash": baseline_strategy_hash,
            "ledger_dir": config["baseline_ledger_dir"],
            "ledger_hash": baseline_hash,
            "trade_count": len(ledger_rows),
            "metrics": baseline_metrics,
            "current_gate_status": _gate_status(baseline_metrics),
        },
        "failure_decomposition": config["failure_decomposition"],
        "experiments": config["experiments"],
    }

    if len(ledger_rows) < int(config["constraints"]["minimum_trades_before_parameter_sweep"]):
        manifest["optimization_mode"] = "NO_PARAMETER_SWEEP_INSUFFICIENT_TRADES"
        manifest["optimization_note"] = "Single fixed hypotheses only; no sweep, no combined optimization."
    else:
        manifest["optimization_mode"] = "FIXED_HYPOTHESIS_EVALUATION"

    results: list[dict[str, Any]] = []
    weights = dict(config["ranking_weights"])
    for experiment in config["experiments"]:
        predicate, resolved_rule = _filter_for(dict(experiment["fixed_rule"]))
        rows = [row for row in ledger_rows if predicate(row)]
        metrics = _normalized_baseline_metrics(rows)
        retention = len(rows) / len(ledger_rows) if ledger_rows else 0.0
        robustness = _robustness_score(rows)
        delta = {
            "pf_2x": _finite(metrics["pf_2x"]) - _finite(baseline_metrics["pf_2x"]),
            "sharpe": _finite(metrics["sharpe_2x"]) - _finite(baseline_metrics["sharpe_2x"]),
            "drawdown_r": _finite(baseline_metrics["drawdown_r_2x"]) - _finite(metrics["drawdown_r_2x"]),
            "trade_count": len(rows) - len(ledger_rows),
            "robustness": robustness - baseline_robustness,
        }
        score = _ranking_score(delta, retention, delta["robustness"], weights)
        results.append(
            {
                "experiment_id": experiment["experiment_id"],
                "name": experiment["name"],
                "hypothesis": experiment["hypothesis"],
                "source_cause": experiment["source_cause"],
                "fixed_rule": resolved_rule,
                "trade_count": len(rows),
                "trade_count_retention": retention,
                "pf_standard": metrics["pf_standard"],
                "pf_2x": metrics["pf_2x"],
                "sharpe_standard": metrics["sharpe_standard"],
                "sharpe_2x": metrics["sharpe_2x"],
                "drawdown_r_standard": metrics["drawdown_r_standard"],
                "drawdown_r_2x": metrics["drawdown_r_2x"],
                "expectancy_2x": metrics["expectancy_2x"],
                "robustness": robustness,
                "delta_pf_2x": delta["pf_2x"],
                "delta_sharpe": delta["sharpe"],
                "drawdown_reduction_r": delta["drawdown_r"],
                "delta_robustness": delta["robustness"],
                "ranking_score": score,
                "classification": _classification(delta, retention, len(rows)),
                "current_gate_status": _gate_status(metrics),
            }
        )

    results.sort(key=lambda row: (row["ranking_score"], row["delta_pf_2x"], row["trade_count"]), reverse=True)
    for idx, row in enumerate(results, start=1):
        row["rank"] = idx

    comparison_rows = [
        {
            "experiment_id": row["experiment_id"],
            "name": row["name"],
            "trade_count": row["trade_count"],
            "trade_count_retention": f"{row['trade_count_retention']:.6f}",
            "pf_2x": f"{row['pf_2x']:.6f}",
            "delta_pf_2x": f"{row['delta_pf_2x']:.6f}",
            "sharpe_2x": f"{row['sharpe_2x']:.6f}",
            "delta_sharpe": f"{row['delta_sharpe']:.6f}",
            "drawdown_r_2x": f"{row['drawdown_r_2x']:.6f}",
            "drawdown_reduction_r": f"{row['drawdown_reduction_r']:.6f}",
            "robustness": f"{row['robustness']:.6f}",
            "classification": row["classification"],
            "current_gate_status": row["current_gate_status"],
        }
        for row in results
    ]
    ranking_rows = [
        {
            "rank": row["rank"],
            "experiment_id": row["experiment_id"],
            "name": row["name"],
            "ranking_score": f"{row['ranking_score']:.6f}",
            "delta_pf_2x": f"{row['delta_pf_2x']:.6f}",
            "delta_sharpe": f"{row['delta_sharpe']:.6f}",
            "drawdown_reduction_r": f"{row['drawdown_reduction_r']:.6f}",
            "trade_count_retention": f"{row['trade_count_retention']:.6f}",
            "delta_robustness": f"{row['delta_robustness']:.6f}",
            "classification": row["classification"],
            "current_gate_status": row["current_gate_status"],
        }
        for row in results
    ]

    outputs = {
        "experiment_manifest": output_dir / "experiment_manifest.yaml",
        "experiment_results": output_dir / "experiment_results.json",
        "experiment_comparison": output_dir / "experiment_comparison.csv",
        "experiment_rankings": output_dir / "experiment_rankings.csv",
        "recommendation_report": output_dir / "recommendation_report.md",
        "baseline_freeze": output_dir / "baseline_freeze.json",
    }
    outputs["experiment_manifest"].write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    write_json(outputs["baseline_freeze"], manifest["baseline"])
    write_json(outputs["experiment_results"], {"created_at": _now(), "baseline": baseline_metrics, "results": results})
    _write_csv(outputs["experiment_comparison"], comparison_rows, list(comparison_rows[0].keys()))
    _write_csv(outputs["experiment_rankings"], ranking_rows, list(ranking_rows[0].keys()))
    _report(results, outputs["recommendation_report"], baseline_metrics, manifest)

    return {
        "status": "COMPLETE",
        "baseline_trade_count": len(ledger_rows),
        "optimization_mode": manifest["optimization_mode"],
        "outputs": {name: str(path.relative_to(ROOT)) for name, path in outputs.items()},
        "top_ranked": results[0]["experiment_id"] if results else None,
        "validated": [row["experiment_id"] for row in results if row["classification"] == "VALIDATED"],
        "rejected": [row["experiment_id"] for row in results if row["classification"] == "REJECTED"],
        "requires_additional_data": [row["experiment_id"] for row in results if row["classification"] == "REQUIRES_ADDITIONAL_DATA"],
    }
