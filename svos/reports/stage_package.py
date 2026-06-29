from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from svos.reports.evidence_package import build_stage_evidence

SCHEMA_VERSION = "2.0.0"

PUBLIC_STAGES = (
    ("strategy_audit", "Strategy Audit", "01_strategy_audit"),
    ("historical_replay", "Historical Replay", "02_historical_replay"),
    ("backtest", "Backtest", "03_backtest"),
    ("robustness", "Robustness Tests", "04_robustness"),
    ("virtual_demo", "Virtual Demo", "05_virtual_demo"),
    ("production_approval", "Production Approval", "06_production_approval"),
)

_SOURCE_STAGES = {
    "strategy_audit": ("intake", "audit", "enhancement"),
    "historical_replay": ("replay",),
    "backtest": ("backtest",),
    "robustness": ("robustness",),
    "virtual_demo": ("verification_ready", "virtual_demo"),
    "production_approval": ("production_approval",),
}

_REMEDIATION_ROUTES = {
    "strategy_audit": "strategy_audit",
    "historical_replay": "strategy_audit",
    "backtest": "backtest",
    "robustness": "robustness",
    "virtual_demo": "research",
    "production_approval": "production_approval",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_payload(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _safe_component(value: str, fallback: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-.")
    return cleaned or fallback


def _issue_dict(issue: Any) -> dict[str, Any]:
    if isinstance(issue, dict):
        return dict(issue)
    if hasattr(issue, "__dataclass_fields__"):
        return asdict(issue)
    return {"code": "unknown", "message": str(issue), "severity": "HIGH"}


def _stage_dict(stage: Any) -> dict[str, Any]:
    if isinstance(stage, dict):
        return dict(stage)
    if hasattr(stage, "to_dict"):
        return stage.to_dict()
    if hasattr(stage, "__dataclass_fields__"):
        return asdict(stage)
    raise TypeError(f"Unsupported stage result: {type(stage)!r}")


def _is_missing_evidence(stage: dict[str, Any]) -> bool:
    codes = {str(item.get("code", "")) for item in stage.get("issues", []) if isinstance(item, dict)}
    if "missing_input" in codes:
        return True
    return bool(codes) and all(
        "missing" in code or "incomplete" in code or "short_window" in code
        for code in codes
    )


def _public_status(source: list[dict[str, Any]], public_stage: str) -> str:
    if not source:
        return "NOT_RUN"
    if public_stage == "virtual_demo" and not any(item.get("stage") == "virtual_demo" for item in source):
        return "NOT_RUN"
    statuses = {str(item.get("status", "")).upper() for item in source}
    if statuses == {"PASS"}:
        return "PASS"
    if any(_is_missing_evidence(item) for item in source if str(item.get("status", "")).upper() != "PASS"):
        return "BLOCKED"
    return "FAIL"


def _checks(source: list[dict[str, Any]]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for item in source:
        metadata = item.get("metadata", {}) if isinstance(item.get("metadata"), dict) else {}
        validation = metadata.get("validation", {}) if isinstance(metadata.get("validation"), dict) else {}
        for check in validation.get("checks", []):
            if isinstance(check, dict):
                checks.append(
                    {
                        "name": str(check.get("name", "validation_check")),
                        "passed": bool(check.get("passed", False)),
                        "hard_gate": str(check.get("severity", "ERROR")).upper() == "ERROR",
                        "message": str(check.get("message", "")),
                        "details": check.get("details", {}),
                    }
                )
        validation_report = metadata.get("validation_report", {}) if isinstance(metadata.get("validation_report"), dict) else {}
        for result in validation_report.get("validator_results", []):
            if isinstance(result, dict):
                checks.append(
                    {
                        "name": str(result.get("validator_name", "audit_validator")),
                        "passed": str(result.get("status", "")).upper() == "PASS",
                        "hard_gate": True,
                        "message": f"Score {result.get('score', 0)}",
                        "details": {"score": result.get("score", 0)},
                    }
                )
        raw_checks = metadata.get("checks", {})
        if isinstance(raw_checks, dict):
            for name, passed in raw_checks.items():
                checks.append(
                    {
                        "name": str(name),
                        "passed": passed is True,
                        "hard_gate": True,
                        "message": "Required robustness check",
                        "details": {"value": passed},
                    }
                )
    if not checks:
        for item in source:
            checks.append(
                {
                    "name": f"{item.get('stage', 'stage')}_gate",
                    "passed": str(item.get("status", "")).upper() == "PASS",
                    "hard_gate": True,
                    "message": "SVOS stage gate result",
                    "details": {},
                }
            )
    return checks


def _score(source: list[dict[str, Any]], checks: list[dict[str, Any]]) -> float | None:
    for item in source:
        metadata = item.get("metadata", {}) if isinstance(item.get("metadata"), dict) else {}
        value = metadata.get("overall_score")
        if isinstance(value, (int, float)):
            return round(float(value), 2)
    if not source or not checks:
        return None
    return round(100.0 * sum(1 for check in checks if check["passed"]) / len(checks), 2)


def _metrics(public_stage: str, source: list[dict[str, Any]]) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    for item in source:
        metadata = item.get("metadata", {}) if isinstance(item.get("metadata"), dict) else {}
        validation = metadata.get("validation", {}) if isinstance(metadata.get("validation"), dict) else {}
        for key, value in validation.get("metadata", {}).items() if isinstance(validation.get("metadata"), dict) else []:
            metrics[key] = value
        if public_stage in {"historical_replay", "backtest"}:
            for check in validation.get("checks", []):
                if not isinstance(check, dict) or not isinstance(check.get("details"), dict):
                    continue
                metrics.update(check["details"])
        if public_stage == "strategy_audit":
            report = metadata.get("validation_report", {}) if isinstance(metadata.get("validation_report"), dict) else {}
            metrics.update(
                {
                    "overall_score": report.get("overall_score"),
                    "critical_issue_count": len(report.get("critical_issues", [])),
                    "warning_count": len(report.get("warnings", [])),
                }
            )
        elif public_stage == "robustness":
            metrics.update({"regression": metadata.get("regression"), "checks": metadata.get("checks", {})})
        elif public_stage == "virtual_demo" and item.get("stage") == "virtual_demo":
            metrics.update(
                {
                    "days_monitored": metadata.get("days_monitored"),
                    "minimum_days": metadata.get("min_demo_days"),
                    "expected_metrics": metadata.get("research_metrics", {}),
                    "observed_metrics": metadata.get("live_metrics", {}),
                    "execution": metadata.get("virtual_demo_evidence", {}),
                }
            )
        elif public_stage == "production_approval":
            metrics.update(
                {
                    "registry_approved": metadata.get("registry_approved"),
                    "live_promotion_allowed": metadata.get("live_promotion_allowed"),
                }
            )
    return {key: value for key, value in metrics.items() if value is not None}


def _thresholds(public_stage: str, source: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, Any]:
    if public_stage == "strategy_audit":
        return {"minimum_readiness_score": 85, "critical_ambiguities_allowed": 0}
    if public_stage == "backtest":
        return {
            "minimum_trade_count": config.get("minimum_trade_count"),
            "minimum_profit_factor": config.get("minimum_profit_factor"),
            "maximum_drawdown": config.get("maximum_drawdown"),
            "minimum_expectancy": config.get("minimum_expectancy"),
        }
    if public_stage == "robustness":
        return {
            "required_checks": [
                "walk_forward_passed",
                "monte_carlo_passed",
                "parameter_stability_passed",
                "regime_analysis_passed",
                "execution_cost_passed",
            ],
            "regression_thresholds": config.get("regression_thresholds", {}),
        }
    if public_stage == "virtual_demo":
        demo = next((item for item in source if item.get("stage") == "virtual_demo"), {})
        metadata = demo.get("metadata", {}) if isinstance(demo.get("metadata"), dict) else {}
        evidence = metadata.get("virtual_demo_evidence", {}) if isinstance(metadata.get("virtual_demo_evidence"), dict) else {}
        return {
            "minimum_days": metadata.get("min_demo_days", 14),
            "metric_drift_tolerance": evidence.get("tolerance_pct", 0.05),
            "minimum_execution_score": 90,
        }
    return {}


def _virtual_demo_route(source: list[dict[str, Any]]) -> str:
    codes = {
        str(issue.get("code", ""))
        for item in source
        for issue in item.get("issues", [])
        if isinstance(issue, dict)
    }
    if any("version" in code for code in codes):
        return "strategy_audit"
    if any("metric_drift" in code or "drawdown_drift" in code for code in codes):
        return "backtest"
    if any("execution" in code or "broker" in code or "recovery" in code for code in codes):
        return "robustness"
    return "research"


def _render_stage(report: dict[str, Any]) -> str:
    lines = [
        f"# SVOS {report['stage_label']} Report",
        "",
        f"- Strategy: `{report['strategy_id']}`",
        f"- Version: `{report['strategy_version']}`",
        f"- Run: `{report['run_id']}`",
        f"- Status: **{report['status']}**",
        f"- Diagnostic Score: `{report['score'] if report['score'] is not None else 'n/a'}`",
        f"- Promotion Allowed: `{str(report['promotion_allowed']).lower()}`",
        f"- Generated: `{report['generated_at']}`",
        "",
        "## Gate Results",
        "",
        "| Check | Result | Hard Gate | Message |",
        "|---|---|---|---|",
    ]
    for check in report["hard_gate_results"]:
        message = str(check.get("message", "")).replace("|", "\\|")
        lines.append(
            f"| {check['name']} | {'PASS' if check['passed'] else 'FAIL'} | "
            f"{'yes' if check['hard_gate'] else 'no'} | {message} |"
        )
    if report["findings"]:
        lines.extend(["", "## Findings", ""])
        for finding in report["findings"]:
            lines.append(f"- {finding.get('severity', 'INFO')}: {finding.get('message', '')}")
    lines.extend(
        [
            "",
            "## Remediation",
            "",
            f"- Route: `{report['remediation']['route']}`",
        ]
    )
    for action in report["remediation"]["actions"]:
        lines.append(f"- {action}")
    if report["metrics"]:
        lines.extend(["", "## Metrics"])
        _append_markdown_value(lines, report["metrics"])
    sections = report.get("sections", {})
    for key in (
        "executive_summary",
        "objective",
        "scope",
        "inputs",
        "evaluation_results",
        "evidence",
        "issues",
        "recommendations",
        "decision",
        "next_action",
        "appendices",
    ):
        if key not in sections:
            continue
        lines.extend(["", f"## {_humanize(key)}"])
        _append_markdown_value(lines, sections[key])
    if report.get("visualizations"):
        lines.extend(["", "## Visualization Data"])
        for visualization in report["visualizations"]:
            lines.extend(["", f"### {visualization.get('title', 'Chart')}"])
            _append_markdown_value(lines, {key: value for key, value in visualization.items() if key not in {"title", "type"}})
    return "\n".join(lines) + "\n"


def _humanize(value: str) -> str:
    return value.replace("_", " ").title()


def _scalar(value: Any) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))


def _display(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, bool):
        return "yes" if value else "no"
    return str(value).replace("|", "\\|").replace("\n", " ")


def _append_markdown_value(lines: list[str], value: Any) -> None:
    if _scalar(value):
        lines.extend(["", _display(value)])
        return
    if isinstance(value, dict):
        if all(_scalar(item) for item in value.values()):
            lines.extend(["", "| Metric | Value |", "|---|---:|"])
            for key, item in value.items():
                lines.append(f"| {_humanize(str(key))} | {_display(item)} |")
            return
        for key, item in value.items():
            lines.extend(["", f"### {_humanize(str(key))}"])
            _append_markdown_value(lines, item)
        return
    if isinstance(value, list):
        if not value:
            lines.extend(["", "No evidence recorded."])
            return
        if all(isinstance(item, dict) for item in value):
            keys = list(dict.fromkeys(key for item in value for key in item.keys()))
            if keys and all(_scalar(item.get(key)) for item in value for key in keys):
                lines.extend(["", "| " + " | ".join(_humanize(str(key)) for key in keys) + " |", "|" + "---|" * len(keys)])
                for item in value:
                    lines.append("| " + " | ".join(_display(item.get(key)) for key in keys) + " |")
                return
        lines.append("")
        for item in value:
            if _scalar(item):
                lines.append(f"- {_display(item)}")
            else:
                lines.extend(["```json", json.dumps(item, indent=2, sort_keys=True, default=str), "```"])
        return
    lines.extend(["", "```json", json.dumps(value, indent=2, sort_keys=True, default=str), "```"])


def _render_summary(summary: dict[str, Any]) -> str:
    lines = [
        "# SVOS Run Summary",
        "",
        f"- Strategy: `{summary['strategy_id']}`",
        f"- Version: `{summary['strategy_version']}`",
        f"- Run: `{summary['run_id']}`",
        f"- Overall Status: **{summary['overall_status']}**",
        f"- Latest Passed Stage: `{summary['latest_passed_stage'] or 'none'}`",
        f"- Active Blocker: `{summary['active_blocker'] or 'none'}`",
        f"- Next Task: {summary['next_task']}",
        "",
        "| Stage | Status | Score | Promotion |",
        "|---|---|---:|---|",
    ]
    for stage in summary["stages"]:
        score = stage["score"] if stage["score"] is not None else "n/a"
        lines.append(f"| {stage['stage_label']} | {stage['status']} | {score} | {'yes' if stage['promotion_allowed'] else 'no'} |")
    return "\n".join(lines) + "\n"


def _render_supporting(report: dict[str, Any]) -> str:
    lines = [
        f"# SVOS {report['title']}",
        "",
        f"- Strategy: `{report['strategy_id']}`",
        f"- Version: `{report['strategy_version']}`",
        f"- Run: `{report['run_id']}`",
        f"- Report Type: `{report['report_type']}`",
    ]
    for key, value in report.get("sections", {}).items():
        lines.extend(["", f"## {_humanize(str(key))}"])
        _append_markdown_value(lines, value)
    return "\n".join(lines) + "\n"


def _write_supporting_report(
    report_dir: Path,
    stem: str,
    *,
    title: str,
    report_type: str,
    run_id: str,
    strategy_id: str,
    strategy_version: str,
    generated_at: str,
    sections: dict[str, Any],
) -> dict[str, Any]:
    report = {
        "schema_version": SCHEMA_VERSION,
        "report_id": f"{strategy_id}:{strategy_version}:{run_id}:{report_type}",
        "report_type": report_type,
        "title": title,
        "run_id": run_id,
        "strategy_id": strategy_id,
        "strategy_version": strategy_version,
        "generated_at": generated_at,
        "sections": sections,
    }
    json_path = report_dir / f"{stem}.json"
    markdown_path = report_dir / f"{stem}.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8")
    markdown_path.write_text(_render_supporting(report), encoding="utf-8")
    return {**report, "json_path": str(json_path), "markdown_path": str(markdown_path)}


@dataclass(frozen=True)
class StageReportPackage:
    run_id: str
    strategy_id: str
    strategy_version: str
    report_dir: Path
    summary_json: Path
    summary_markdown: Path
    stage_artifacts: tuple[dict[str, Any], ...]
    supporting_artifacts: tuple[dict[str, Any], ...]


def write_stage_report_package(
    *,
    output_root: Path,
    strategy_name: str,
    strategy_id: str,
    strategy_version: str,
    strategy_text: str,
    stages: list[Any],
    promoted_stage: str | None,
    validation_config: dict[str, Any],
    input_payloads: dict[str, Any],
    release: dict[str, Any],
    previous_version: str | None = None,
) -> StageReportPackage:
    generated_at = _now()
    input_hashes = {name: _hash_payload(value) for name, value in input_payloads.items() if value is not None}
    input_hashes["validation_config"] = _hash_payload(validation_config)
    spec_hash = hashlib.sha256(strategy_text.encode("utf-8")).hexdigest()
    run_seed = {"strategy": strategy_id, "version": strategy_version, "generated_at": generated_at, "inputs": input_hashes}
    stamp = datetime.fromisoformat(generated_at).strftime("%Y%m%dT%H%M%S.%fZ")
    run_id = f"{stamp}-{_hash_payload(run_seed)[:10]}"
    report_dir = (
        output_root
        / _safe_component(strategy_id, "strategy")
        / _safe_component(strategy_version, "0.0.0")
        / run_id
    )
    report_dir.mkdir(parents=True, exist_ok=False)

    internal = [_stage_dict(stage) for stage in stages]
    internal_by_name = {str(stage.get("stage", "")): stage for stage in internal}
    reports: list[dict[str, Any]] = []
    upstream_blocker = ""
    latest_passed = ""

    for public_stage, label, stem in PUBLIC_STAGES:
        source = [internal_by_name[name] for name in _SOURCE_STAGES[public_stage] if name in internal_by_name]
        status = "BLOCKED" if upstream_blocker else _public_status(source, public_stage)
        checks = _checks(source) if source else []
        findings = [_issue_dict(issue) for item in source for issue in item.get("issues", [])]
        actions = [str(action) for item in source for action in item.get("fix_instructions", []) if str(action).strip()]
        if status == "BLOCKED" and upstream_blocker and not actions:
            actions = [f"Resolve the {upstream_blocker} gate before running {label}."]
        route = _virtual_demo_route(source) if public_stage == "virtual_demo" and status == "FAIL" else _REMEDIATION_ROUTES[public_stage]
        source_allows_promotion = bool(source) and all(bool(item.get("can_promote", False)) for item in source)
        promotion_allowed = (
            status == "PASS"
            and source_allows_promotion
            and all(check["passed"] for check in checks if check["hard_gate"])
        )
        metrics = _metrics(public_stage, source)
        thresholds = _thresholds(public_stage, source, validation_config)
        evidence_hashes = {"strategy_spec": spec_hash, **input_hashes}
        payload_key = {
            "historical_replay": "replay",
            "backtest": "backtest",
            "robustness": "robustness",
            "virtual_demo": "virtual_demo",
            "production_approval": "production_approval",
        }.get(public_stage, "")
        raw_payload = input_payloads.get(payload_key) if payload_key else {}
        if not isinstance(raw_payload, dict):
            raw_payload = {}
        sections, visualizations = build_stage_evidence(
            public_stage=public_stage,
            label=label,
            status=status,
            score=_score(source, checks),
            promotion_allowed=promotion_allowed,
            source=source,
            checks=checks,
            findings=findings,
            actions=list(dict.fromkeys(actions)),
            metrics=metrics,
            thresholds=thresholds,
            raw_payload=raw_payload,
            evidence_hashes=evidence_hashes,
            prior_reports=reports,
        )
        report = {
            "schema_version": SCHEMA_VERSION,
            "report_id": f"{strategy_id}:{strategy_version}:{run_id}:{public_stage}",
            "run_id": run_id,
            "strategy_name": strategy_name,
            "strategy_id": strategy_id,
            "strategy_version": strategy_version,
            "stage": public_stage,
            "stage_label": label,
            "status": status,
            "score": _score(source, checks),
            "promotion_allowed": promotion_allowed,
            "thresholds": thresholds,
            "hard_gate_results": checks,
            "metrics": metrics,
            "findings": findings,
            "warnings": [finding for finding in findings if str(finding.get("severity", "")).upper() in {"WARN", "WARNING", "MEDIUM"}],
            "evidence_hashes": evidence_hashes,
            "remediation": {"route": route, "actions": list(dict.fromkeys(actions))},
            "version_comparison": {
                "previous_version": previous_version,
                "current_version": strategy_version,
                "changed": bool(previous_version and previous_version != strategy_version),
            },
            "internal_sources": [item.get("stage") for item in source],
            "sections": sections,
            "visualizations": visualizations,
            "generated_at": generated_at,
            "release": release,
        }
        json_path = report_dir / f"{stem}.json"
        markdown_path = report_dir / f"{stem}.md"
        json_path.write_text(json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8")
        markdown_path.write_text(_render_stage(report), encoding="utf-8")
        reports.append({**report, "json_path": str(json_path), "markdown_path": str(markdown_path)})
        if status == "PASS":
            latest_passed = public_stage
        elif status in {"FAIL", "BLOCKED"} and not upstream_blocker:
            upstream_blocker = public_stage

    audit_source = internal_by_name.get("audit", {})
    audit_spec = audit_source.get("spec", {}) if isinstance(audit_source.get("spec"), dict) else {}
    strategy_fields = audit_spec.get("fields", {}) if isinstance(audit_spec.get("fields"), dict) else {}
    stage_overview = [
        {"stage": report["stage_label"], "status": report["status"], "score": report["score"]}
        for report in reports
    ]
    supporting: list[dict[str, Any]] = []
    supporting.append(
        _write_supporting_report(
            report_dir,
            "00_strategy_summary",
            title="New Strategy Summary",
            report_type="strategy_summary",
            run_id=run_id,
            strategy_id=strategy_id,
            strategy_version=strategy_version,
            generated_at=generated_at,
            sections={
                "strategy_information": {
                    "strategy_id": strategy_id,
                    "strategy_name": strategy_name,
                    "version": strategy_version,
                    "market": strategy_fields.get("market"),
                    "session": strategy_fields.get("session"),
                    "risk": strategy_fields.get("risk"),
                    "entry": strategy_fields.get("entry_trigger"),
                    "confirmation": strategy_fields.get("confirmation"),
                    "stop_loss": strategy_fields.get("stop_loss"),
                    "take_profit": strategy_fields.get("take_profit"),
                },
                "stage_overview": stage_overview,
                "current_position": {
                    "status": "IN_PROGRESS" if any(report["status"] != "PASS" for report in reports) else "QUALIFIED",
                    "current_stage": next((report["stage_label"] for report in reports if report["status"] != "PASS"), "Production Approval"),
                },
            },
        )
    )

    failed_reports = [report for report in reports if report["status"] in {"FAIL", "BLOCKED"}]
    improvement_items = [
        {
            "stage": report["stage_label"],
            "route": report["remediation"]["route"],
            "actions": report["remediation"]["actions"],
        }
        for report in failed_reports
    ]
    supporting.append(
        _write_supporting_report(
            report_dir,
            "strategy_evolution",
            title="Strategy Evolution Report",
            report_type="strategy_evolution",
            run_id=run_id,
            strategy_id=strategy_id,
            strategy_version=strategy_version,
            generated_at=generated_at,
            sections={
                "version_history": {
                    "previous_version": previous_version,
                    "current_version": strategy_version,
                    "changed": bool(previous_version and previous_version != strategy_version),
                },
                "evidence_change": {"strategy_spec_hash": spec_hash, "input_hashes": input_hashes},
                "reason": "Immutable SVOS validation snapshot.",
            },
        )
    )
    supporting.append(
        _write_supporting_report(
            report_dir,
            "failure_analysis",
            title="Failure Analysis Report",
            report_type="failure_analysis",
            run_id=run_id,
            strategy_id=strategy_id,
            strategy_version=strategy_version,
            generated_at=generated_at,
            sections={
                "failure_count": len(failed_reports),
                "failure_chain": [
                    {
                        "stage": report["stage_label"],
                        "status": report["status"],
                        "issues": report["findings"],
                        "cause_route": report["remediation"]["route"],
                    }
                    for report in failed_reports
                ],
                "result": "NO_FAILURES" if not failed_reports else "ACTION_REQUIRED",
            },
        )
    )
    supporting.append(
        _write_supporting_report(
            report_dir,
            "improvement_report",
            title="Improvement Report",
            report_type="improvement",
            run_id=run_id,
            strategy_id=strategy_id,
            strategy_version=strategy_version,
            generated_at=generated_at,
            sections={
                "status": "NO_ACTION_REQUIRED" if not improvement_items else "ACTION_REQUIRED",
                "recommended_changes": improvement_items,
                "revalidation_required": bool(improvement_items),
            },
        )
    )

    active = next((report for report in reports if report["status"] in {"FAIL", "BLOCKED"}), None)
    pending = next((report for report in reports if report["status"] in {"NOT_RUN", "IN_PROGRESS"}), None)
    focus = active or pending
    overall_status = "PASS" if all(report["status"] == "PASS" for report in reports) else (active["status"] if active else "IN_PROGRESS")
    next_task = "No further validation task." if focus is None else (
        focus["remediation"]["actions"][0]
        if focus["remediation"]["actions"]
        else f"Complete the {focus['stage_label']} stage."
    )
    summary = {
        "schema_version": SCHEMA_VERSION,
        "report_id": f"{strategy_id}:{strategy_version}:{run_id}:summary",
        "run_id": run_id,
        "strategy_name": strategy_name,
        "strategy_id": strategy_id,
        "strategy_version": strategy_version,
        "overall_status": overall_status,
        "latest_passed_stage": latest_passed,
        "active_blocker": active["stage"] if active else "",
        "next_task": next_task,
        "promoted_stage": promoted_stage,
        "evidence_hashes": {"strategy_spec": spec_hash, **input_hashes},
        "stages": [
            {
                "stage": report["stage"],
                "stage_label": report["stage_label"],
                "status": report["status"],
                "score": report["score"],
                "promotion_allowed": report["promotion_allowed"],
                "report_id": report["report_id"],
                "json_path": report["json_path"],
                "markdown_path": report["markdown_path"],
            }
            for report in reports
        ],
        "report_center": {
            "strategy_summary": supporting[0]["report_id"],
            "strategy_evolution": supporting[1]["report_id"],
            "failure_analysis": supporting[2]["report_id"],
            "improvement_report": supporting[3]["report_id"],
        },
        "generated_at": generated_at,
        "release": release,
    }
    summary_json = report_dir / "run_summary.json"
    summary_markdown = report_dir / "run_summary.md"
    summary_json.write_text(json.dumps(summary, indent=2, sort_keys=True, default=str), encoding="utf-8")
    summary_markdown.write_text(_render_summary(summary), encoding="utf-8")
    supporting.append(
        _write_supporting_report(
            report_dir,
            "final_qualification",
            title="Final Qualification Report",
            report_type="final_qualification",
            run_id=run_id,
            strategy_id=strategy_id,
            strategy_version=strategy_version,
            generated_at=generated_at,
            sections={
                "lifecycle_summary": stage_overview,
                "overall_status": overall_status,
                "overall_score": round(
                    sum(float(report["score"]) for report in reports if report["score"] is not None)
                    / max(1, sum(1 for report in reports if report["score"] is not None)),
                    2,
                ),
                "latest_passed_stage": latest_passed,
                "active_blocker": active["stage"] if active else None,
                "final_decision": "QUALIFIED" if overall_status == "PASS" else "NOT_QUALIFIED",
                "next_action": next_task,
                "production_monitoring": "NOT_STARTED - generated only after real production deployment",
            },
        )
    )
    return StageReportPackage(
        run_id=run_id,
        strategy_id=strategy_id,
        strategy_version=strategy_version,
        report_dir=report_dir,
        summary_json=summary_json,
        summary_markdown=summary_markdown,
        stage_artifacts=tuple(reports),
        supporting_artifacts=tuple(supporting),
    )
