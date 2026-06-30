"""Canonical paired JSON + Markdown report builders.

Every pipeline stage produces:
  - a machine-readable JSON artifact (the evidence source of truth)
  - a deterministic Markdown rendering of the same JSON

Both share a report_id. Regenerating Markdown cannot change the underlying
decision or evidence. The JSON artifact is registered with the artifact store
and evidence repository; Markdown is a human-readable companion only.

Stage-specific builders in this module:
  IntakeReportBuilder     — Phase 0 Intake validation report
  AuditReportBuilder      — Phase 1 Strategy Audit report
  ReplayReportBuilder     — Phase 2 Historical Replay report
  BacktestReportBuilder   — Phase 3 Backtest and Statistical Validation report
  RobustnessReportBuilder — Phase 4 Robustness Validation report
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from svos.shared.support import now_iso, stable_manifest_hash


_SCHEMA_VERSION = "1.0"


# ═══════════════════════════════════════════════════════════════════════════
# Intake — Phase 0
# ═══════════════════════════════════════════════════════════════════════════


class IntakeReportBuilder:
    """Builds the canonical Phase-0 Intake report pair (JSON + Markdown)."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.reports_root = self.root / "data" / "svos" / "reports" / "intake"

    def build_intake_report(
        self,
        *,
        strategy: str,
        version_id: str,
        status: str,
        findings: list[dict[str, Any]],
        specification_hash: str = "",
        manifest: dict[str, Any] | None = None,
        catalog: dict[str, Any] | None = None,
    ) -> Path:
        """Write JSON + Markdown and return the JSON path (registered as evidence artifact)."""
        generated_at = now_iso()
        errors = [f for f in findings if f.get("severity") == "ERROR"]
        warnings = [f for f in findings if f.get("severity") == "WARN"]

        payload: dict[str, Any] = {
            "report_type": "intake_report",
            "schema_version": _SCHEMA_VERSION,
            "stage": "INTAKE",
            "strategy": strategy,
            "version_id": version_id,
            "status": status,
            "generated_at": generated_at,
            "specification_hash": specification_hash,
            "summary": {
                "error_count": len(errors),
                "warning_count": len(warnings),
                "finding_count": len(findings),
            },
            "findings": findings,
            "catalog": catalog or {},
            "run_manifest": manifest or {},
        }
        report_id = stable_manifest_hash({"strategy": strategy, "version_id": version_id, "generated_at": generated_at})
        payload["report_id"] = report_id

        dest_dir = self.reports_root / strategy
        dest_dir.mkdir(parents=True, exist_ok=True)
        json_path = dest_dir / f"intake_{report_id[:16]}.json"
        md_path = dest_dir / f"intake_{report_id[:16]}.md"

        json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        md_path.write_text(_render_intake_md(payload), encoding="utf-8")

        return json_path


def _render_intake_md(report: dict[str, Any]) -> str:
    status = report["status"]
    icon = "✅" if status == "PASS" else "❌"
    findings = report.get("findings", [])
    errors = [f for f in findings if f.get("severity") == "ERROR"]
    warnings = [f for f in findings if f.get("severity") == "WARN"]

    sections = [
        f"# Intake Report — {report['strategy']}",
        "",
        f"**Status:** {icon} {status}  ",
        f"**Generated:** {report['generated_at']}  ",
        f"**Version ID:** `{report['version_id']}`  ",
        f"**Report ID:** `{report['report_id']}`  ",
        "",
        "## Summary",
        "",
        f"- Errors: {len(errors)}",
        f"- Warnings: {len(warnings)}",
        f"- Specification hash: `{report.get('specification_hash', '')[:20]}…`",
    ]

    if findings:
        sections += ["", "## Findings", ""]
        for f in findings:
            sev = f.get("severity", "INFO")
            prefix = "🔴" if sev == "ERROR" else "🟡" if sev == "WARN" else "ℹ️"
            sections.append(f"- {prefix} **[{f.get('code', '')}]** {f.get('message', '')}")

    catalog = report.get("catalog", {})
    if catalog:
        sections += ["", "## Catalog Entry", ""]
        for key, value in sorted(catalog.items()):
            sections.append(f"- **{key}:** {value}")

    sections += ["", f"*Schema version {report['schema_version']}*"]
    return "\n".join(sections) + "\n"


# ═══════════════════════════════════════════════════════════════════════════
# Audit — Phase 1
# ═══════════════════════════════════════════════════════════════════════════


class AuditReportBuilder:
    """Builds the canonical Phase-1 Strategy Audit report pair (JSON + Markdown)."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.reports_root = self.root / "data" / "svos" / "reports" / "audit"

    def build_audit_report(
        self,
        *,
        strategy: str,
        version_id: str,
        status: str,
        overall_score: float,
        readiness_decision: str,
        validator_results: list[dict[str, Any]],
        critical_issues: list[str],
        warnings: list[str],
        recommendations: list[dict[str, Any]],
        manifest: dict[str, Any] | None = None,
    ) -> Path:
        """Write JSON + Markdown and return the JSON path."""
        generated_at = now_iso()

        payload: dict[str, Any] = {
            "report_type": "audit_report",
            "schema_version": _SCHEMA_VERSION,
            "stage": "AUDIT",
            "strategy": strategy,
            "version_id": version_id,
            "status": status,
            "generated_at": generated_at,
            "overall_score": round(overall_score, 2),
            "readiness_decision": readiness_decision,
            "summary": {
                "critical_issue_count": len(critical_issues),
                "warning_count": len(warnings),
                "validator_count": len(validator_results),
                "recommendation_count": len(recommendations),
            },
            "critical_issues": critical_issues,
            "warnings": warnings,
            "recommendations": recommendations,
            "validator_results": validator_results,
            "run_manifest": manifest or {},
        }
        report_id = stable_manifest_hash({"strategy": strategy, "version_id": version_id, "generated_at": generated_at})
        payload["report_id"] = report_id

        dest_dir = self.reports_root / strategy
        dest_dir.mkdir(parents=True, exist_ok=True)
        json_path = dest_dir / f"audit_{report_id[:16]}.json"
        md_path = dest_dir / f"audit_{report_id[:16]}.md"

        json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        md_path.write_text(_render_audit_md(payload), encoding="utf-8")

        return json_path


def _render_audit_md(report: dict[str, Any]) -> str:
    status = report["status"]
    icon = "✅" if status == "PASS" else "❌"
    score = report.get("overall_score", 0.0)
    decision = report.get("readiness_decision", "")
    critical = report.get("critical_issues", [])
    warnings = report.get("warnings", [])
    recommendations = report.get("recommendations", [])
    validators = report.get("validator_results", [])

    sections = [
        f"# Strategy Audit Report — {report['strategy']}",
        "",
        f"**Status:** {icon} {status}  ",
        f"**Score:** {score:.1f}%  ",
        f"**Decision:** {decision}  ",
        f"**Generated:** {report['generated_at']}  ",
        f"**Version ID:** `{report['version_id']}`  ",
        f"**Report ID:** `{report['report_id']}`  ",
        "",
        "## Summary",
        "",
        f"- Validators run: {len(validators)}",
        f"- Critical issues: {len(critical)}",
        f"- Warnings: {len(warnings)}",
        f"- Recommendations: {len(recommendations)}",
    ]

    if critical:
        sections += ["", "## Critical Issues", ""]
        for issue in critical:
            sections.append(f"- 🔴 {issue}")

    if warnings:
        sections += ["", "## Warnings", ""]
        for w in warnings:
            sections.append(f"- 🟡 {w}")

    if validators:
        sections += ["", "## Validator Results", "", "| Validator | Score | Status |", "|-----------|-------|--------|"]
        for v in validators:
            sections.append(f"| {v.get('validator_name', '')} | {v.get('score', 0):.1f}% | {v.get('status', '')} |")

    if recommendations:
        sections += ["", "## Recommendations", ""]
        for rec in recommendations:
            pri = rec.get("priority", "MEDIUM")
            prefix = "🔴" if pri == "HIGH" else "🟡" if pri == "MEDIUM" else "ℹ️"
            sections.append(f"- {prefix} {rec.get('message', '')}")

    sections += ["", f"*Schema version {report['schema_version']}*"]
    return "\n".join(sections) + "\n"


# ═══════════════════════════════════════════════════════════════════════════
# Replay — Phase 2
# ═══════════════════════════════════════════════════════════════════════════


class ReplayReportBuilder:
    """Builds the canonical Phase-2 Historical Replay report pair (JSON + Markdown)."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.reports_root = self.root / "data" / "svos" / "reports" / "replay"

    def build_replay_report(
        self,
        *,
        strategy: str,
        version_id: str,
        status: str,
        checks: list[dict[str, Any]],
        trade_count: int = 0,
        replay_summary: dict[str, Any] | None = None,
        manifest: dict[str, Any] | None = None,
    ) -> Path:
        generated_at = now_iso()
        passed_checks = sum(1 for c in checks if c.get("passed"))
        failed_checks = sum(1 for c in checks if not c.get("passed"))

        payload: dict[str, Any] = {
            "report_type": "replay_report",
            "schema_version": _SCHEMA_VERSION,
            "stage": "HISTORICAL_REPLAY",
            "strategy": strategy,
            "version_id": version_id,
            "status": status,
            "generated_at": generated_at,
            "trade_count": trade_count,
            "summary": {
                "passed_checks": passed_checks,
                "failed_checks": failed_checks,
                "total_checks": len(checks),
            },
            "checks": checks,
            "replay_summary": replay_summary or {},
            "run_manifest": manifest or {},
        }
        report_id = stable_manifest_hash({"strategy": strategy, "version_id": version_id, "generated_at": generated_at})
        payload["report_id"] = report_id

        dest_dir = self.reports_root / strategy
        dest_dir.mkdir(parents=True, exist_ok=True)
        json_path = dest_dir / f"replay_{report_id[:16]}.json"
        md_path = dest_dir / f"replay_{report_id[:16]}.md"

        json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        md_path.write_text(_render_replay_md(payload), encoding="utf-8")
        return json_path


def _render_replay_md(report: dict[str, Any]) -> str:
    status = report["status"]
    icon = "✅" if status == "PASS" else "❌"
    checks = report.get("checks", [])
    summary = report.get("summary", {})
    sections = [
        f"# Historical Replay Report — {report['strategy']}",
        "",
        f"**Status:** {icon} {status}  ",
        f"**Trade Count:** {report.get('trade_count', 0)}  ",
        f"**Generated:** {report['generated_at']}  ",
        f"**Version ID:** `{report['version_id']}`  ",
        "",
        "## Summary",
        "",
        f"- Checks passed: {summary.get('passed_checks', 0)} / {summary.get('total_checks', 0)}",
        f"- Checks failed: {summary.get('failed_checks', 0)}",
    ]
    if checks:
        sections += ["", "## Checks", "", "| Check | Status | Message |", "|-------|--------|---------|"]
        for c in checks:
            s = "PASS" if c.get("passed") else "FAIL"
            msg = str(c.get("message", "")).replace("|", "\\|")
            sections.append(f"| {c.get('name', '')} | {s} | {msg} |")
    sections += ["", f"*Schema version {report['schema_version']}*"]
    return "\n".join(sections) + "\n"


# ═══════════════════════════════════════════════════════════════════════════
# Backtest — Phase 3
# ═══════════════════════════════════════════════════════════════════════════


class BacktestReportBuilder:
    """Builds the canonical Phase-3 Backtest / Statistical Validation report."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.reports_root = self.root / "data" / "svos" / "reports" / "backtest"

    def build_backtest_report(
        self,
        *,
        strategy: str,
        version_id: str,
        status: str,
        checks: list[dict[str, Any]],
        metrics: dict[str, Any] | None = None,
        cost_model: dict[str, Any] | None = None,
        manifest: dict[str, Any] | None = None,
    ) -> Path:
        generated_at = now_iso()
        m = metrics or {}
        passed_checks = sum(1 for c in checks if c.get("passed"))
        failed_checks = sum(1 for c in checks if not c.get("passed"))

        payload: dict[str, Any] = {
            "report_type": "backtest_report",
            "schema_version": _SCHEMA_VERSION,
            "stage": "STATISTICAL_VALIDATION",
            "strategy": strategy,
            "version_id": version_id,
            "status": status,
            "generated_at": generated_at,
            "summary": {
                "passed_checks": passed_checks,
                "failed_checks": failed_checks,
                "total_checks": len(checks),
                "trade_count": int(m.get("trade_count", 0)),
                "profit_factor": float(m.get("profit_factor", 0.0)),
                "profit_factor_2x": float(m.get("profit_factor_2x", 0.0)),
                "expectancy": float(m.get("expectancy", 0.0)),
                "max_drawdown": float(m.get("max_drawdown", 0.0)),
                "win_rate": float(m.get("win_rate", 0.0)),
            },
            "metrics": m,
            "cost_model": cost_model or {},
            "checks": checks,
            "run_manifest": manifest or {},
        }
        report_id = stable_manifest_hash({"strategy": strategy, "version_id": version_id, "generated_at": generated_at})
        payload["report_id"] = report_id

        dest_dir = self.reports_root / strategy
        dest_dir.mkdir(parents=True, exist_ok=True)
        json_path = dest_dir / f"backtest_{report_id[:16]}.json"
        md_path = dest_dir / f"backtest_{report_id[:16]}.md"

        json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        md_path.write_text(_render_backtest_md(payload), encoding="utf-8")
        return json_path


def _render_backtest_md(report: dict[str, Any]) -> str:
    status = report["status"]
    icon = "✅" if status == "PASS" else "❌"
    s = report.get("summary", {})
    checks = report.get("checks", [])
    sections = [
        f"# Backtest Report — {report['strategy']}",
        "",
        f"**Status:** {icon} {status}  ",
        f"**Generated:** {report['generated_at']}  ",
        f"**Version ID:** `{report['version_id']}`  ",
        "",
        "## Key Metrics",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Trade count | {s.get('trade_count', 0)} |",
        f"| Profit factor (standard) | {s.get('profit_factor', 0):.3f} |",
        f"| Profit factor (2× stress) | {s.get('profit_factor_2x', 0):.3f} |",
        f"| Expectancy | {s.get('expectancy', 0):.4f} R |",
        f"| Max drawdown | {s.get('max_drawdown', 0):.2f}% |",
        f"| Win rate | {s.get('win_rate', 0):.1%} |",
    ]
    if checks:
        sections += ["", "## Gate Checks", "", "| Check | Status | Message |", "|-------|--------|---------|"]
        for c in checks:
            s2 = "PASS" if c.get("passed") else "FAIL"
            msg = str(c.get("message", "")).replace("|", "\\|")
            sections.append(f"| {c.get('name', '')} | {s2} | {msg} |")
    sections += ["", f"*Schema version {report['schema_version']}*"]
    return "\n".join(sections) + "\n"


# ═══════════════════════════════════════════════════════════════════════════
# Robustness — Phase 4
# ═══════════════════════════════════════════════════════════════════════════


class RobustnessReportBuilder:
    """Builds the canonical Phase-4 Robustness Validation report."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.reports_root = self.root / "data" / "svos" / "reports" / "robustness"

    def build_robustness_report(
        self,
        *,
        strategy: str,
        version_id: str,
        status: str,
        walk_forward: dict[str, Any] | None = None,
        monte_carlo: dict[str, Any] | None = None,
        sensitivity: dict[str, Any] | None = None,
        regime: dict[str, Any] | None = None,
        manifest: dict[str, Any] | None = None,
    ) -> Path:
        generated_at = now_iso()
        components = {
            "walk_forward": walk_forward or {},
            "monte_carlo": monte_carlo or {},
            "parameter_sensitivity": sensitivity or {},
            "regime_analysis": regime or {},
        }
        component_statuses = {
            name: ("PASS" if (data.get("passed") or data.get("status") == "PASS") else "FAIL")
            for name, data in components.items()
            if data
        }
        payload: dict[str, Any] = {
            "report_type": "robustness_report",
            "schema_version": _SCHEMA_VERSION,
            "stage": "ROBUSTNESS_VALIDATION",
            "strategy": strategy,
            "version_id": version_id,
            "status": status,
            "generated_at": generated_at,
            "summary": {
                "component_count": len([d for d in components.values() if d]),
                "components_passed": sum(1 for s in component_statuses.values() if s == "PASS"),
                "components_failed": sum(1 for s in component_statuses.values() if s == "FAIL"),
            },
            "component_statuses": component_statuses,
            "components": components,
            "run_manifest": manifest or {},
        }
        report_id = stable_manifest_hash({"strategy": strategy, "version_id": version_id, "generated_at": generated_at})
        payload["report_id"] = report_id

        dest_dir = self.reports_root / strategy
        dest_dir.mkdir(parents=True, exist_ok=True)
        json_path = dest_dir / f"robustness_{report_id[:16]}.json"
        md_path = dest_dir / f"robustness_{report_id[:16]}.md"

        json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        md_path.write_text(_render_robustness_md(payload), encoding="utf-8")
        return json_path


class VirtualDemoReportBuilder:
    """Builds the canonical JSON + Markdown virtual demo report."""

    def __init__(self, root: Any) -> None:
        root_path = Path(root) if not isinstance(root, Path) else root
        self.reports_root = root_path / "data" / "svos" / "reports" / "virtual_demo"

    def build_virtual_demo_report(
        self,
        *,
        strategy: str,
        version_id: str,
        status: str,
        drift_checks: list[dict[str, Any]],
        summary: dict[str, Any],
        manifest: dict[str, Any] | None = None,
    ) -> Path:
        generated_at = now_iso()
        payload: dict[str, Any] = {
            "schema_version": _SCHEMA_VERSION,
            "report_type": "virtual_demo_report",
            "stage": "VIRTUAL_DEMO",
            "strategy": strategy,
            "version_id": version_id,
            "status": status,
            "generated_at": generated_at,
            "drift_checks": drift_checks,
            "summary": summary,
            "run_manifest": manifest or {},
        }
        report_id = stable_manifest_hash({"strategy": strategy, "version_id": version_id, "generated_at": generated_at})
        payload["report_id"] = report_id

        dest_dir = self.reports_root / strategy
        dest_dir.mkdir(parents=True, exist_ok=True)
        json_path = dest_dir / f"virtual_demo_{report_id[:16]}.json"
        md_path = dest_dir / f"virtual_demo_{report_id[:16]}.md"

        json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        md_path.write_text(_render_virtual_demo_md(payload), encoding="utf-8")
        return json_path


def _render_robustness_md(report: dict[str, Any]) -> str:
    status = report["status"]
    icon = "✅" if status == "PASS" else "❌"
    s = report.get("summary", {})
    comp_statuses = report.get("component_statuses", {})
    sections = [
        f"# Robustness Report — {report['strategy']}",
        "",
        f"**Status:** {icon} {status}  ",
        f"**Generated:** {report['generated_at']}  ",
        f"**Version ID:** `{report['version_id']}`  ",
        "",
        "## Component Summary",
        "",
        f"- Components run: {s.get('component_count', 0)}",
        f"- Passed: {s.get('components_passed', 0)}",
        f"- Failed: {s.get('components_failed', 0)}",
    ]
    if comp_statuses:
        sections += ["", "## Component Results", "", "| Component | Status |", "|-----------|--------|"]
        for name, cs in comp_statuses.items():
            cs_icon = "✅" if cs == "PASS" else "❌"
            sections.append(f"| {name.replace('_', ' ').title()} | {cs_icon} {cs} |")
    sections += ["", f"*Schema version {report['schema_version']}*"]
    return "\n".join(sections) + "\n"


def _render_virtual_demo_md(report: dict[str, Any]) -> str:
    status = report["status"]
    icon = "✅" if status == "PASS" else "❌"
    s = report.get("summary", {})
    checks = report.get("drift_checks", [])
    fill_rate = s.get("fill_rate", 0)
    fill_pct = f"{fill_rate:.1%}" if isinstance(fill_rate, (int, float)) else str(fill_rate)
    sections = [
        f"# Virtual Demo Report — {report['strategy']}",
        "",
        f"**Status:** {icon} {status}  ",
        f"**Generated:** {report['generated_at']}  ",
        f"**Version ID:** `{report['version_id']}`  ",
        "",
        "## Execution Summary",
        "",
        f"- Signals submitted: {s.get('signal_count', 0)}",
        f"- Orders filled: {s.get('filled_count', 0)}",
        f"- Fill rate: {fill_pct}",
        f"- Virtual profit factor: {s.get('virtual_pf', 0):.3f}",
        f"- Expected profit factor: {s.get('expected_pf') or 'N/A'}",
    ]
    if checks:
        sections += ["", "## Drift Checks", "", "| Check | Pass | Expected | Actual | Delta % |",
                     "|-------|------|----------|--------|---------|"]
        for c in checks:
            ok = "✅" if c.get("passed") else "❌"
            sections.append(
                f"| {c['name']} | {ok} | {c.get('expected', '')} | {c.get('actual', '')} | {c.get('delta_pct', '')}% |"
            )
    sections += ["", f"*Schema version {report['schema_version']}*"]
    return "\n".join(sections) + "\n"
