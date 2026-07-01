#!/usr/bin/env python3
"""Render a compact SVOS registry audit in JSON, Markdown, and HTML."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from svos.governance.service import GovernanceService
from svos.registry.service import StrategyRegistryService


def build_audit(root: Path) -> dict:
    registry = StrategyRegistryService(root=root)
    governance = GovernanceService(root=root, registry=registry)
    summary = registry.summary()
    strategies: list[dict] = []
    for item in summary.get("strategies", []):
        strategy = str(item.get("strategy", ""))
        strategies.append(
            {
                "strategy": strategy,
                "current_stage": item.get("current_stage", ""),
                "latest_version": item.get("latest_version", ""),
                "version_count": item.get("version_count", 0),
                "evidence_count": item.get("evidence_count", 0),
                "transition_count": item.get("transition_count", 0),
                "decision_count": len(governance.decisions(strategy)),
                "approval_count": len(governance.approvals(strategy)),
            }
        )
    return {
        "strategy_count": len(strategies),
        "strategies": strategies,
    }


def render_markdown(audit: dict) -> str:
    lines = [
        "# Registry Audit",
        "",
        f"- Strategy count: {audit['strategy_count']}",
        "",
        "| Strategy | Stage | Version | Evidence | Decisions | Approvals |",
        "| --- | --- | --- | ---: | ---: | ---: |",
    ]
    for item in audit["strategies"]:
        lines.append(
            f"| {item['strategy']} | {item['current_stage']} | {item['latest_version']} | "
            f"{item['evidence_count']} | {item['decision_count']} | {item['approval_count']} |"
        )
    return "\n".join(lines) + "\n"


def render_html(audit: dict) -> str:
    rows = []
    for item in audit["strategies"]:
        rows.append(
            "<tr>"
            f"<td>{item['strategy']}</td>"
            f"<td>{item['current_stage']}</td>"
            f"<td>{item['latest_version']}</td>"
            f"<td>{item['evidence_count']}</td>"
            f"<td>{item['decision_count']}</td>"
            f"<td>{item['approval_count']}</td>"
            "</tr>"
        )
    return (
        "<html><body><h1>Registry Audit</h1>"
        f"<p>Strategy count: {audit['strategy_count']}</p>"
        "<table border='1' cellspacing='0' cellpadding='4'>"
        "<thead><tr><th>Strategy</th><th>Stage</th><th>Version</th><th>Evidence</th><th>Decisions</th><th>Approvals</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
        "</body></html>"
    )


def write_outputs(audit: dict, outdir: Path) -> list[Path]:
    outdir.mkdir(parents=True, exist_ok=True)
    outputs = {
        outdir / "registry_audit.json": json.dumps(audit, indent=2, sort_keys=True) + "\n",
        outdir / "registry_audit.md": render_markdown(audit),
        outdir / "registry_audit.html": render_html(audit),
    }
    for path, content in outputs.items():
        path.write_text(content, encoding="utf-8")
    return list(outputs.keys())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Repository root")
    parser.add_argument("--outdir", default="reports/registry_audit", help="Audit output directory")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    outputs = write_outputs(build_audit(root), (root / args.outdir).resolve())
    for path in outputs:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
