from __future__ import annotations

import hashlib
import json
import math
import random
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median, pstdev
from typing import Any

import yaml

from research.research_validation import git_state, load_trade_ledger, load_yaml, write_json
from research.st_a2_freeze import STRATEGY_CONFIG, _ledger_hash, canonical_strategy_hash

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "config" / "robustness" / "st_a2_v2_candidate.yaml"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def _r_values(rows: list[dict[str, Any]], cost_multiplier: float = 1.0) -> list[float]:
    return [_finite(row.get("gross_pnl")) - (_cost(row) * cost_multiplier) for row in rows]


def _pf(values: list[float]) -> float:
    wins = sum(value for value in values if value > 0)
    losses = abs(sum(value for value in values if value < 0))
    if losses == 0:
        return float("inf") if wins > 0 else 0.0
    return wins / losses


def _max_drawdown(values: list[float]) -> float:
    running = peak = worst = 0.0
    for value in values:
        running += value
        peak = max(peak, running)
        worst = max(worst, peak - running)
    return worst


def _sharpe(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    sd = pstdev(values)
    return mean(values) / sd * math.sqrt(len(values)) if sd else 0.0


def _metrics(rows: list[dict[str, Any]], cost_multiplier: float = 1.0) -> dict[str, Any]:
    values = _r_values(rows, cost_multiplier)
    wins = [value for value in values if value > 0]
    return {
        "trade_count": len(values),
        "net_r": sum(values),
        "profit_factor": _pf(values),
        "sharpe": _sharpe(values),
        "max_drawdown_r": _max_drawdown(values),
        "expectancy": mean(values) if values else 0.0,
        "win_rate": len(wins) / len(values) if values else 0.0,
    }


def _quantile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * q))))
    return ordered[idx]


def _candidate_rows(rows: list[dict[str, Any]], config: dict[str, Any]) -> list[dict[str, Any]]:
    rule = config["selection_rule"]
    if rule["type"] != "exclude_symbol":
        raise ValueError(f"Unsupported candidate selection rule: {rule['type']}")
    excluded = str(rule["symbol"])
    return [row for row in rows if str(row.get("symbol")) != excluded]


def _gate(metrics_std: dict[str, Any], metrics_2x: dict[str, Any], gate: dict[str, Any]) -> dict[str, Any]:
    checks = {
        "trades": int(metrics_std["trade_count"]) > int(gate["min_trades"]),
        "pf_standard": _finite(metrics_std["profit_factor"]) > float(gate["min_pf_standard"]),
        "pf_2x": _finite(metrics_2x["profit_factor"]) > float(gate["min_pf_2x"]),
        "sharpe_standard": _finite(metrics_std["sharpe"]) > float(gate["min_sharpe_standard"]),
        "sharpe_2x": _finite(metrics_2x["sharpe"]) > float(gate["min_sharpe_2x"]),
        "drawdown_standard": _finite(metrics_std["max_drawdown_r"]) < float(gate["max_drawdown_r"]),
        "drawdown_2x": _finite(metrics_2x["max_drawdown_r"]) < float(gate["max_drawdown_r"]),
    }
    return {"status": "PASS" if all(checks.values()) else "FAIL", "checks": checks}


def _walk_forward(rows: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, Any]:
    windows = []
    passed = True
    for window in config["robustness"]["walk_forward_windows"]:
        subset = [
            row
            for row in rows
            if str(window["start"]) <= str(row.get("entry_time") or "")[:10] <= str(window["end"])
        ]
        std = _metrics(subset, 1.0)
        stress = _metrics(subset, 2.0)
        window_passed = std["trade_count"] >= 30 and stress["profit_factor"] > 1.0 and stress["expectancy"] > 0
        passed = passed and window_passed
        windows.append({**window, "metrics_standard": std, "metrics_2x": stress, "passed": window_passed})
    return {
        "created_at": _now(),
        "status": "PASS" if passed and windows else "FAIL",
        "rule": "Each fixed time window must have n>=30, PF_2x>1.0, expectancy_2x>0.",
        "windows": windows,
    }


def _monte_carlo(rows: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, Any]:
    iterations = int(config["robustness"]["monte_carlo_iterations"])
    seed = int(config["robustness"]["seed"])
    values = _r_values(rows, 2.0)
    if len(values) < 50:
        return {"created_at": _now(), "status": "INSUFFICIENT_DATA", "sample_count": len(values), "iterations": 0}
    rng = random.Random(seed)
    pfs: list[float] = []
    sharpes: list[float] = []
    drawdowns: list[float] = []
    net_rs: list[float] = []
    for _ in range(iterations):
        sample = [values[rng.randrange(len(values))] for _ in range(len(values))]
        pfs.append(_pf(sample))
        sharpes.append(_sharpe(sample))
        drawdowns.append(_max_drawdown(sample))
        net_rs.append(sum(sample))
    status = "PASS" if _quantile(pfs, 0.05) > 1.0 and _quantile(net_rs, 0.05) > 0 and _quantile(drawdowns, 0.95) < 20.0 else "FAIL"
    return {
        "created_at": _now(),
        "status": status,
        "seed": seed,
        "iterations": iterations,
        "sample_count": len(values),
        "profit_factor": {"p05": _quantile(pfs, 0.05), "median": median(pfs), "p95": _quantile(pfs, 0.95)},
        "sharpe": {"p05": _quantile(sharpes, 0.05), "median": median(sharpes), "p95": _quantile(sharpes, 0.95)},
        "max_drawdown_r": {"p50": median(drawdowns), "p95": _quantile(drawdowns, 0.95)},
        "net_r": {"p05": _quantile(net_rs, 0.05), "median": median(net_rs), "p95": _quantile(net_rs, 0.95)},
    }


def _bootstrap(rows: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, Any]:
    iterations = int(config["robustness"]["bootstrap_iterations"])
    seed = int(config["robustness"]["seed"]) + 17
    values = _r_values(rows, 2.0)
    if len(values) < 50:
        return {"status": "INSUFFICIENT_DATA", "sample_count": len(values), "iterations": 0}
    rng = random.Random(seed)
    expectancies = []
    win_rates = []
    for _ in range(iterations):
        sample = [values[rng.randrange(len(values))] for _ in range(len(values))]
        expectancies.append(mean(sample))
        win_rates.append(len([value for value in sample if value > 0]) / len(sample))
    return {
        "status": "PASS" if _quantile(expectancies, 0.05) > 0 else "FAIL",
        "seed": seed,
        "iterations": iterations,
        "expectancy_2x": {"p05": _quantile(expectancies, 0.05), "median": median(expectancies), "p95": _quantile(expectancies, 0.95)},
        "win_rate_2x": {"p05": _quantile(win_rates, 0.05), "median": median(win_rates), "p95": _quantile(win_rates, 0.95)},
    }


def _sensitivity(rows: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, Any]:
    scenarios = []
    for multiplier in config["robustness"]["cost_stress_multipliers"]:
        metrics = _metrics(rows, float(multiplier))
        scenarios.append({"cost_multiplier": float(multiplier), "metrics": metrics})
    return {
        "created_at": _now(),
        "status": "PASS" if all(row["metrics"]["profit_factor"] > 1.0 for row in scenarios) else "FAIL",
        "mode": "fixed_cost_stress_only_no_parameter_search",
        "scenarios": scenarios,
    }


def _write_report(path: Path, expanded: dict[str, Any], walk: dict[str, Any], mc: dict[str, Any], sens: dict[str, Any], final_status: str) -> None:
    c = expanded["candidate"]
    lines = [
        "# ST-A2_v2 Candidate Robustness Report",
        "",
        f"Generated: {expanded['created_at']}",
        "",
        "## Candidate",
        "",
        f"- Candidate: `{expanded['candidate_id']}`",
        f"- Source experiment: `{expanded['source_experiment']}`",
        f"- Rule: exclude `{expanded['selection_rule']['symbol']}`",
        f"- Available net trades: {c['metrics_standard']['trade_count']}",
        f"- Expansion target: {expanded['evidence_targets']['minimum_net_trades']}-{expanded['evidence_targets']['recommended_net_trades']} trades",
        f"- Expansion status: {expanded['expansion_status']}",
        "",
        "## Metrics",
        "",
        f"- PF standard: {c['metrics_standard']['profit_factor']:.4f}",
        f"- PF 2x: {c['metrics_2x']['profit_factor']:.4f}",
        f"- Sharpe standard: {c['metrics_standard']['sharpe']:.4f}",
        f"- Sharpe 2x: {c['metrics_2x']['sharpe']:.4f}",
        f"- MaxDD standard: {c['metrics_standard']['max_drawdown_r']:.4f}R",
        f"- MaxDD 2x: {c['metrics_2x']['max_drawdown_r']:.4f}R",
        f"- Phase-3 gate: {c['phase3_gate']['status']}",
        "",
        "## Robustness",
        "",
        f"- Walk-forward: {walk['status']}",
        f"- Monte Carlo: {mc['status']}",
        f"- Bootstrap: {mc.get('bootstrap', {}).get('status')}",
        f"- Sensitivity: {sens['status']}",
        "",
        "## Decision",
        "",
        final_status,
        "",
        "ST-A2_v1 remains immutable. ST-A2_v2_candidate is candidate-only and is not eligible for demo trading from this evidence.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def run_st_a2_v2_candidate_robustness(config_path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    config = load_yaml(config_path)
    outdir = _resolve(config["artifact_root"])
    outdir.mkdir(parents=True, exist_ok=True)
    baseline_rows = load_trade_ledger(_resolve(config["baseline_ledger_dir"]))
    candidate_rows = _candidate_rows(baseline_rows, config)
    baseline_std = _metrics(baseline_rows, 1.0)
    baseline_2x = _metrics(baseline_rows, 2.0)
    candidate_std = _metrics(candidate_rows, 1.0)
    candidate_2x = _metrics(candidate_rows, 2.0)
    gate = _gate(candidate_std, candidate_2x, config["phase3_gate"])
    evidence_targets = config["evidence_targets"]
    expansion_status = (
        "TARGET_MET"
        if candidate_std["trade_count"] >= int(evidence_targets["minimum_net_trades"])
        else "REQUIRES_ADDITIONAL_DATA"
    )
    expanded = {
        "created_at": _now(),
        "candidate_id": config["candidate_id"],
        "source_experiment": config["source_experiment"],
        "git": git_state(),
        "constraints": config["constraints"],
        "selection_rule": config["selection_rule"],
        "strategy": {
            "baseline_config": config["baseline_config"],
            "baseline_config_sha256": _sha256(_resolve(config["baseline_config"])),
            "baseline_strategy_hash": canonical_strategy_hash(STRATEGY_CONFIG),
            "candidate_version": config["candidate_version"],
        },
        "ledger": {
            "baseline_ledger_hash": _ledger_hash(baseline_rows),
            "candidate_ledger_hash": _ledger_hash(candidate_rows),
        },
        "evidence_targets": evidence_targets,
        "expansion_status": expansion_status,
        "baseline": {"metrics_standard": baseline_std, "metrics_2x": baseline_2x},
        "candidate": {"metrics_standard": candidate_std, "metrics_2x": candidate_2x, "phase3_gate": gate},
    }
    walk = _walk_forward(candidate_rows, config)
    mc = _monte_carlo(candidate_rows, config)
    mc["bootstrap"] = _bootstrap(candidate_rows, config)
    sens = _sensitivity(candidate_rows, config)
    final_status = "REQUIRES_ADDITIONAL_DATA"
    if expansion_status == "TARGET_MET":
        final_status = "PASS" if gate["status"] == "PASS" and walk["status"] == "PASS" and mc["status"] == "PASS" and sens["status"] == "PASS" else "FAIL"

    outputs = {
        "expanded_metrics": outdir / "expanded_metrics.json",
        "walk_forward_results": outdir / "walk_forward_results.json",
        "monte_carlo_results": outdir / "monte_carlo_results.json",
        "sensitivity_results": outdir / "sensitivity_results.json",
        "robustness_report": outdir / "robustness_report.md",
    }
    write_json(outputs["expanded_metrics"], expanded)
    write_json(outputs["walk_forward_results"], walk)
    write_json(outputs["monte_carlo_results"], mc)
    write_json(outputs["sensitivity_results"], sens)
    _write_report(outputs["robustness_report"], expanded, walk, mc, sens, final_status)
    return {
        "status": final_status,
        "candidate_trade_count": candidate_std["trade_count"],
        "expansion_status": expansion_status,
        "phase3_gate": gate["status"],
        "outputs": {key: str(path.relative_to(ROOT)) for key, path in outputs.items()},
    }
