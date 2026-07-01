from __future__ import annotations

import html
import json
from pathlib import Path

from ..models import ValidationReport


class ReportGenerator:
    def build_json(self, report: ValidationReport) -> str:
        return json.dumps(report.to_dict(), indent=2, sort_keys=True, default=str)

    def build_markdown(self, report: ValidationReport) -> str:
        lines = [
            "# Strategy Specification Validation Report",
            "",
            f"- Strategy: `{report.strategy_name}`",
            f"- Overall Status: **{report.overall_status}**",
            f"- Overall Score: **{report.overall_score:.1f}%**",
            f"- Readiness Decision: **{report.readiness_decision}**",
            f"- Source: `{report.source_path or 'inline'}`",
            f"- Document Hash: `{report.document_hash}`",
            "",
            report.summary,
            "",
            "## Audit Summary",
            "",
            f"- Ambiguous rules: **{report.summary_counts.ambiguous_rule_count}**",
            f"- Missing parameters: **{report.summary_counts.missing_parameter_count}**",
            f"- Contradictions: **{report.summary_counts.contradiction_count}**",
            f"- Undefined filters: **{report.summary_counts.undefined_filter_count}**",
            f"- Execution conflicts: **{report.summary_counts.execution_conflict_count}**",
            "",
            "## Issue Buckets",
        ]
        if report.issue_buckets.fatal_blockers:
            lines.extend(["", "### Fatal Blockers"])
            lines.extend([f"- {item}" for item in report.issue_buckets.fatal_blockers])
        if report.issue_buckets.revision_required_issues:
            lines.extend(["", "### Revision Required"])
            lines.extend([f"- {item}" for item in report.issue_buckets.revision_required_issues])
        if report.issue_buckets.improvement_only_recommendations:
            lines.extend(["", "### Improvement-Only Recommendations"])
            lines.extend([f"- {item}" for item in report.issue_buckets.improvement_only_recommendations])
        lines.extend(
            [
                "",
                "## Validator Results",
            ]
        )
        for result in report.validator_results:
            lines.extend(
                [
                    f"### {result.validator_name}",
                    f"- Status: **{result.status}**",
                    f"- Score: `{result.score:.1f}`",
                ]
            )
            for finding in result.findings:
                lines.append(f"- {finding.severity}: {finding.message}")
            for recommendation in result.recommendations[:4]:
                lines.append(f"- Recommendation: {recommendation.message}")
        if report.critical_issues:
            lines.extend(["", "## Critical Issues"])
            lines.extend([f"- {item}" for item in report.critical_issues])
        if report.warnings:
            lines.extend(["", "## Warnings"])
            lines.extend([f"- {item}" for item in report.warnings])
        if report.recommendations:
            lines.extend(["", "## Improvement Recommendations"])
            for item in report.recommendations:
                lines.append(f"- {item.message}")
        return "\n".join(lines).strip() + "\n"

    def build_html(self, report: ValidationReport) -> str:
        rows = []
        for result in report.validator_results:
            rows.append(
                "<tr>"
                f"<td>{html.escape(result.validator_name)}</td>"
                f"<td>{html.escape(result.status)}</td>"
                f"<td>{result.score:.1f}</td>"
                f"<td>{html.escape('; '.join(f.message for f in result.findings[:3]))}</td>"
                "</tr>"
            )
        summary_rows = [
            ("Ambiguous rules", report.summary_counts.ambiguous_rule_count),
            ("Missing parameters", report.summary_counts.missing_parameter_count),
            ("Contradictions", report.summary_counts.contradiction_count),
            ("Undefined filters", report.summary_counts.undefined_filter_count),
            ("Execution conflicts", report.summary_counts.execution_conflict_count),
        ]
        issue_sections: list[str] = []
        if report.issue_buckets.fatal_blockers:
            issue_sections.append(
                "<h2>Fatal Blockers</h2><ul>"
                + "".join(f"<li>{html.escape(item)}</li>" for item in report.issue_buckets.fatal_blockers)
                + "</ul>"
            )
        if report.issue_buckets.revision_required_issues:
            issue_sections.append(
                "<h2>Revision Required</h2><ul>"
                + "".join(f"<li>{html.escape(item)}</li>" for item in report.issue_buckets.revision_required_issues)
                + "</ul>"
            )
        if report.issue_buckets.improvement_only_recommendations:
            issue_sections.append(
                "<h2>Improvement-Only Recommendations</h2><ul>"
                + "".join(
                    f"<li>{html.escape(item)}</li>" for item in report.issue_buckets.improvement_only_recommendations
                )
                + "</ul>"
            )
        return (
            "<html><body>"
            "<h1>Strategy Specification Validation Report</h1>"
            f"<p><strong>Strategy:</strong> {html.escape(report.strategy_name)}</p>"
            f"<p><strong>Overall Status:</strong> {html.escape(report.overall_status)}</p>"
            f"<p><strong>Overall Score:</strong> {report.overall_score:.1f}%</p>"
            f"<p><strong>Readiness Decision:</strong> {html.escape(report.readiness_decision)}</p>"
            "<h2>Audit Summary</h2>"
            "<table border='1'><thead><tr><th>Category</th><th>Count</th></tr></thead>"
            f"<tbody>{''.join(f'<tr><td>{html.escape(label)}</td><td>{count}</td></tr>' for label, count in summary_rows)}</tbody></table>"
            f"{''.join(issue_sections)}"
            "<table border='1'><thead><tr><th>Validator</th><th>Status</th><th>Score</th><th>Findings</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table>"
            "</body></html>"
        )

    def write(self, report: ValidationReport, output_dir: Path) -> dict[str, Path]:
        output_dir.mkdir(parents=True, exist_ok=True)
        paths = {
            "json": output_dir / "validation_report.json",
            "markdown": output_dir / "validation_report.md",
            "html": output_dir / "validation_report.html",
            "audit_log": output_dir / "audit_log.json",
        }
        paths["json"].write_text(self.build_json(report), encoding="utf-8")
        paths["markdown"].write_text(self.build_markdown(report), encoding="utf-8")
        paths["html"].write_text(self.build_html(report), encoding="utf-8")
        paths["audit_log"].write_text(json.dumps([item.to_dict() for item in report.audit_log], indent=2), encoding="utf-8")
        return paths
