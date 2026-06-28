from __future__ import annotations

import json
from pathlib import Path

from .models import AuditReport


def build_markdown(report: AuditReport) -> str:
    lines = [
        "# Institutional Strategy Audit",
        "",
        f"- Strategy: `{report.strategy}`",
        f"- Overall Status: **{report.overall_status}**",
        f"- Readiness Score: **{report.readiness_score:.1f}%**",
        f"- Deployment Status: **{report.deployment_status}**",
        f"- Capital Tier: `{report.capital_tier}`",
        f"- Recommended Risk: `{report.recommended_risk_pct:.2f}%`",
        f"- Confidence: `{report.confidence:.1f}%`",
        "",
        "## Module Results",
    ]
    for module in report.module_results:
        lines.extend(
            [
                f"### {module.name}",
                f"- Status: **{module.status}**",
                f"- Score: `{module.score:.1f}`",
            ]
        )
        if module.warnings:
            lines.append("- Warnings:")
            lines.extend([f"  - {item}" for item in module.warnings])
        if module.errors:
            lines.append("- Errors:")
            lines.extend([f"  - {item}" for item in module.errors])
        if module.recommendation:
            lines.append(f"- Recommendation: {module.recommendation}")
    if report.failure_modes:
        lines.extend(["", "## Failure Modes"])
        lines.extend([f"- {item}" for item in report.failure_modes])
    if report.recommendations:
        lines.extend(["", "## Recommendations"])
        lines.extend([f"- {item}" for item in report.recommendations])
    return "\n".join(lines) + "\n"


def build_json(report: AuditReport) -> str:
    return json.dumps(report.to_dict(), indent=2, sort_keys=True, default=str)


def build_html(report: AuditReport) -> str:
    rows = []
    for module in report.module_results:
        rows.append(
            f"<tr><td>{module.name}</td><td>{module.status}</td><td>{module.score:.1f}</td><td>{json.dumps(module.metrics, default=str)}</td></tr>"
        )
    return (
        "<html><body>"
        f"<h1>Institutional Strategy Audit</h1>"
        f"<p><strong>Strategy:</strong> {report.strategy}</p>"
        f"<p><strong>Overall Status:</strong> {report.overall_status}</p>"
        f"<p><strong>Readiness Score:</strong> {report.readiness_score:.1f}%</p>"
        "<table border='1'><thead><tr><th>Module</th><th>Status</th><th>Score</th><th>Metrics</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
        "</body></html>"
    )


def build_pdf(report: AuditReport) -> bytes:
    lines = [
        "Institutional Strategy Audit",
        f"Strategy: {report.strategy}",
        f"Overall Status: {report.overall_status}",
        f"Readiness Score: {report.readiness_score:.1f}%",
        f"Deployment Status: {report.deployment_status}",
    ]
    for module in report.module_results[:15]:
        lines.append(f"{module.name}: {module.status} ({module.score:.1f})")
    return _minimal_pdf(lines)


def _escape_pdf_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _minimal_pdf(lines: list[str]) -> bytes:
    text_lines = "\\n".join(_escape_pdf_text(line) for line in lines)
    content = f"BT /F1 12 Tf 72 760 Td ({text_lines}) Tj ET"
    objects: list[bytes] = []
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
    objects.append(b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>")
    objects.append(f"<< /Length {len(content.encode('latin-1'))} >>\nstream\n{content}\nendstream".encode("latin-1"))
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for idx, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out.extend(f"{idx} 0 obj\n".encode("latin-1"))
        out.extend(obj)
        out.extend(b"\nendobj\n")
    xref = len(out)
    out.extend(f"xref\n0 {len(objects)+1}\n".encode("latin-1"))
    out.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.extend(f"{off:010d} 00000 n \n".encode("latin-1"))
    out.extend(
        (
            f"trailer << /Size {len(objects)+1} /Root 1 0 R >>\n"
            f"startxref\n{xref}\n%%EOF\n"
        ).encode("latin-1")
    )
    return bytes(out)


def write_reports(report: AuditReport, output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "json": output_dir / "audit_report.json",
        "markdown": output_dir / "audit_report.md",
        "html": output_dir / "audit_report.html",
        "pdf": output_dir / "audit_report.pdf",
    }
    paths["json"].write_text(build_json(report), encoding="utf-8")
    paths["markdown"].write_text(build_markdown(report), encoding="utf-8")
    paths["html"].write_text(build_html(report), encoding="utf-8")
    paths["pdf"].write_bytes(build_pdf(report))
    return paths

