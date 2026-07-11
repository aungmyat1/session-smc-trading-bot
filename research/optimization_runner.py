from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from research.research_validation import (
    DEFAULT_BENCHMARK,
    dataset_hash,
    load_yaml,
    optimization_diagnostics,
    trade_metrics,
    walk_forward_report,
    write_json,
)
from research.strategy_diagnostics import DEFAULT_VALIDATION_REPORT, run_diagnostics
from research.st_a2_freeze import STRATEGY_CONFIG, canonical_strategy_hash

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts"
BASELINE_SNAPSHOT = ARTIFACTS / "baseline_strategy_snapshot.json"
EXPERIMENTS_CSV = ARTIFACTS / "optimization_experiments.csv"
COMPARISON_REPORT = ARTIFACTS / "optimization_comparison_report.json"
WF_COMPARISON = ARTIFACTS / "walk_forward_comparison.json"
ROBUSTNESS_COMPARISON = ARTIFACTS / "robustness_comparison.json"
PROMOTION_DECISION = ARTIFACTS / "strategy_promotion_decision.md"

ALLOWED_CHANGE_CATEGORIES = {"entry", "exit", "risk", "filter"}


@dataclass(frozen=True)
class OptimizationExperiment:
    experiment_id: str
    strategy: str
    baseline_version: str
    change: str
    reason: str
    training_period: str
    validation_period: str
    result: str = "PLANNED"
    change_category: str = "entry"

    def validate(self) -> None:
        categories = [part.strip().lower() for part in self.change_category.split("+") if part.strip()]
        if len(categories) != 1 or categories[0] not in ALLOWED_CHANGE_CATEGORIES:
            raise ValueError("Each optimization experiment must change exactly one category: entry, exit, risk, or filter.")

    def to_row(self) -> dict[str, str]:
        self.validate()
        return {
            "experiment_id": self.experiment_id,
            "strategy": self.strategy,
            "baseline_version": self.baseline_version,
            "change_category": self.change_category,
            "change": self.change,
            "reason": self.reason,
            "training_period": self.training_period,
            "validation_period": self.validation_period,
            "result": self.result,
        }


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _file_hash(path: Path) -> str:
    if not path.exists():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _metrics_from_report(report: dict[str, Any]) -> dict[str, Any]:
    metrics = report.get("metrics") if isinstance(report.get("metrics"), dict) else {}
    return {
        "trades": int(float(metrics.get("trades", report.get("trades", 0)) or 0)),
        "win_rate": float(metrics.get("win_rate", report.get("win_rate", 0)) or 0),
        "profit_factor": float(metrics.get("profit_factor_after_cost", metrics.get("profit_factor", report.get("profit_factor", 0))) or 0),
        "sharpe": float(metrics.get("sharpe", report.get("sharpe", 0)) or 0),
        "max_drawdown": float(metrics.get("max_drawdown", report.get("max_drawdown", 0)) or 0),
        "expectancy": float(metrics.get("expectancy", report.get("expectancy", 0)) or 0),
        "average_R": float(metrics.get("average_R", metrics.get("average_r", report.get("average_R", 0))) or 0),
    }


def create_baseline_snapshot(
    strategy: str = "ST-A2",
    validation_report_path: Path = DEFAULT_VALIDATION_REPORT,
    benchmark_path: Path = DEFAULT_BENCHMARK,
    catalog_path: Path = ROOT / "config" / "strategy_catalog.yaml",
    output_path: Path = BASELINE_SNAPSHOT,
) -> dict[str, Any]:
    config = load_yaml(benchmark_path)
    report = _load_json(validation_report_path)
    catalog = yaml.safe_load(catalog_path.read_text(encoding="utf-8")) if catalog_path.exists() else {}
    manifest = ((catalog or {}).get("strategies") or {}).get(strategy, {})
    frozen = yaml.safe_load(STRATEGY_CONFIG.read_text(encoding="utf-8")) if strategy == "ST-A2" and STRATEGY_CONFIG.exists() else {}
    frozen_version = str(frozen.get("version", manifest.get("version", "1.0")))
    spec_path = manifest.get("strategy_spec_path")
    spec_hash = canonical_strategy_hash(STRATEGY_CONFIG) if frozen else (_file_hash(ROOT / str(spec_path)) if spec_path else "")
    parameters_payload = {
        "strategy": strategy,
        "version": frozen_version,
        "symbols": (frozen.get("market", {}) or {}).get("symbols", manifest.get("symbols", [])),
        "timeframes": frozen.get("timeframes", manifest.get("timeframes", [])),
        "requirements": manifest.get("requirements", {}),
        "spec_hash": spec_hash,
    }
    parameters_hash = hashlib.sha256(json.dumps(parameters_payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()
    snapshot = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "strategy": strategy,
        "version": frozen_version,
        "dataset": config.get("dataset", {}).get("version", "professional_3y_4symbol_v2"),
        "dataset_hash": dataset_hash(config),
        "parameters_hash": parameters_hash,
        "parameters": parameters_payload,
        "metrics": _metrics_from_report(report),
        "source_report": str(validation_report_path),
        "status": report.get("status", "MISSING"),
    }
    write_json(output_path, snapshot)
    return snapshot


def seed_experiment_registry(
    diagnosis: dict[str, Any],
    output_path: Path = EXPERIMENTS_CSV,
    strategy: str = "ST-A2",
    baseline_version: str = "1.0",
) -> list[dict[str, str]]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, str]] = []
    category_by_case = {
        "LOW_WIN_RATE_HIGH_RR": "entry",
        "HIGH_WIN_RATE_NEGATIVE_PROFIT": "exit",
        "GOOD_GROSS_BAD_NET": "filter",
        "TOO_FEW_TRADES": "filter",
        "MANY_TRADES_LARGE_DRAWDOWN": "filter",
        "SINGLE_MONTH_DEPENDENCY": "filter",
    }
    failures = diagnosis.get("detected_failures") or []
    if not failures:
        failures = [{"case_id": "NO_FAILURE_DETECTED", "optimization_direction": "No change proposed.", "meaning": "Baseline needs more evidence."}]
    for idx, failure in enumerate(failures, start=1):
        case_id = str(failure.get("case_id", f"CASE_{idx}"))
        experiment = OptimizationExperiment(
            experiment_id=f"OPT-{strategy}-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{idx:02d}",
            strategy=strategy,
            baseline_version=baseline_version,
            change_category=category_by_case.get(case_id, "entry"),
            change=str(failure.get("optimization_direction", "")),
            reason=str(failure.get("meaning", "")),
            training_period="2023-07-01..2025-06-30",
            validation_period="2025-07-01..2025-12-31",
            result="PLANNED",
        )
        rows.append(experiment.to_row())
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return rows


def compare_metrics(baseline: dict[str, Any], candidate: dict[str, Any] | None = None) -> dict[str, Any]:
    base_metrics = baseline.get("metrics", {})
    candidate_metrics = (candidate or {}).get("metrics", {})
    fields = ["profit_factor", "sharpe", "expectancy", "win_rate", "average_R", "max_drawdown"]
    comparison = []
    for field in fields:
        base_value = float(base_metrics.get(field, 0.0) or 0.0)
        candidate_value = float(candidate_metrics.get(field, 0.0) or 0.0)
        comparison.append(
            {
                "metric": field,
                "baseline": base_value,
                "candidate": candidate_value,
                "delta": candidate_value - base_value,
            }
        )
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "NEEDS_MORE_DATA" if not candidate else "COMPARED",
        "performance": comparison,
        "stability": {
            "monthly_returns": (candidate or {}).get("monthly_returns", {}),
            "regime_performance": (candidate or {}).get("regime_performance", {}),
            "symbol_performance": (candidate or {}).get("symbol_performance", {}),
            "session_performance": (candidate or {}).get("session_performance", {}),
        },
        "execution": {
            "gross_pnl": float(candidate_metrics.get("gross_pnl", 0.0) or 0.0),
            "cost": float(candidate_metrics.get("cost", 0.0) or 0.0),
            "net_pnl": float(candidate_metrics.get("net_pnl", 0.0) or 0.0),
            "cost_ratio": float(candidate_metrics.get("cost_ratio", 0.0) or 0.0),
        },
    }


def walk_forward_comparison(candidate_trades_path: Path | None, output_path: Path = WF_COMPARISON) -> dict[str, Any]:
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "training": {"start": "2023-07-01", "end": "2025-06-30"},
        "validation": {"start": "2025-07-01", "end": "2025-12-31"},
        "final_test": {"start": "2026-01-01", "end": "2026-06-30"},
        "status": "NEEDS_MORE_DATA",
        "failure_rule": "Training improvement + validation degradation = FAIL",
    }
    if candidate_trades_path:
        report["candidate"] = walk_forward_report(candidate_trades_path)
        report["status"] = report["candidate"].get("status", "NEEDS_MORE_DATA")
    write_json(output_path, report)
    return report


def robustness_comparison(candidate_summary: dict[str, Any] | None = None, output_path: Path = ROBUSTNESS_COMPARISON) -> dict[str, Any]:
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "NEEDS_MORE_DATA" if not candidate_summary else "COMPARED",
        "spread_stress": "+20%",
        "slippage_stress": "+50%",
        "parameter_perturbation": {"SL": ["5 pip", "6 pip", "7 pip"], "RR": [2, 2.5, 3]},
        "monte_carlo": {"simulations": 1000, "checks": ["drawdown distribution", "probability of ruin", "expected return range"]},
        "candidate": candidate_summary or {},
        "optimization_diagnostics": optimization_diagnostics(),
    }
    write_json(output_path, report)
    return report


def promotion_decision(
    baseline: dict[str, Any],
    candidate: dict[str, Any] | None,
    walk_forward: dict[str, Any],
    output_path: Path = PROMOTION_DECISION,
) -> str:
    decision = "NEEDS_MORE_DATA"
    reasons: list[str] = []
    if candidate:
        base = baseline.get("metrics", {})
        cand = candidate.get("metrics", {})
        pf_ok = float(cand.get("profit_factor", 0.0) or 0.0) > float(base.get("profit_factor", 0.0) or 0.0)
        sharpe_ok = float(cand.get("sharpe", 0.0) or 0.0) > float(base.get("sharpe", 0.0) or 0.0)
        base_dd = float(base.get("max_drawdown", 0.0) or 0.0)
        cand_dd = float(cand.get("max_drawdown", 0.0) or 0.0)
        dd_ok = cand_dd <= base_dd * 1.2 if base_dd > 0 else cand_dd <= 0
        wf_ok = walk_forward.get("status") == "PASS"
        if pf_ok and sharpe_ok and dd_ok and wf_ok:
            decision = "PROMOTE"
        elif not wf_ok:
            decision = "REJECT"
        else:
            decision = "KEEP_BASELINE"
        reasons = [
            f"PF improvement: {'PASS' if pf_ok else 'FAIL'}",
            f"Sharpe improvement: {'PASS' if sharpe_ok else 'FAIL'}",
            f"No DD increase > 20%: {'PASS' if dd_ok else 'FAIL'}",
            f"Walk-forward PASS: {'PASS' if wf_ok else 'FAIL'}",
        ]
    else:
        reasons.append("No candidate metrics supplied.")

    lines = [
        "# Strategy Promotion Decision",
        "",
        f"- Decision: **{decision}**",
        f"- Baseline: {baseline.get('strategy', 'ST-A2')} v{baseline.get('version', '1.0')}",
        "- Candidate: not supplied" if not candidate else f"- Candidate: {candidate.get('strategy', 'UNKNOWN')} v{candidate.get('version', 'UNKNOWN')}",
        "",
        "## Rules",
        "",
        "- PF improvement",
        "- Sharpe improvement",
        "- No DD increase > 20%",
        "- Walk-forward PASS",
        "",
        "## Findings",
        "",
    ]
    lines.extend(f"- {reason}" for reason in reasons)
    lines.extend(["", "No live trading, broker configuration, or deployed strategy settings were changed.", ""])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return decision


def run_framework(
    strategy: str = "ST-A2",
    validation_report_path: Path = DEFAULT_VALIDATION_REPORT,
    candidate_report_path: Path | None = None,
    candidate_trades_path: Path | None = None,
) -> dict[str, Any]:
    baseline = create_baseline_snapshot(strategy=strategy, validation_report_path=validation_report_path)
    diagnosis = run_diagnostics(validation_report_path)
    experiments = seed_experiment_registry(diagnosis, strategy=strategy, baseline_version=str(baseline.get("version", "1.0")))
    candidate = _load_json(candidate_report_path) if candidate_report_path else None
    if candidate:
        candidate = {**candidate, "metrics": _metrics_from_report(candidate)}
    comparison = compare_metrics(baseline, candidate)
    write_json(COMPARISON_REPORT, comparison)
    wf = walk_forward_comparison(candidate_trades_path)
    robust = robustness_comparison()
    decision = promotion_decision(baseline, candidate, wf)
    return {
        "baseline_snapshot": str(BASELINE_SNAPSHOT),
        "strategy_failure_diagnosis": str(ROOT / "artifacts" / "strategy_failure_diagnosis.json"),
        "optimization_experiments": str(EXPERIMENTS_CSV),
        "optimization_comparison_report": str(COMPARISON_REPORT),
        "walk_forward_comparison": str(WF_COMPARISON),
        "robustness_comparison": str(ROBUSTNESS_COMPARISON),
        "strategy_promotion_decision": str(PROMOTION_DECISION),
        "decision": decision,
        "experiment_count": len(experiments),
        "diagnosis_count": len(diagnosis.get("detected_failures", [])),
        "comparison_status": comparison["status"],
        "robustness_status": robust["status"],
    }
