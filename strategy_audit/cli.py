from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .audit_runner import StrategyAuditRunner
from .models import AuditContext
from .report_builder import write_reports


def _load_json(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Strategy Audit Framework")
    parser.add_argument("--strategy", help="Strategy name", default="ST-A2")
    parser.add_argument("--strategy-text", help="Inline strategy text")
    parser.add_argument("--payload", help="JSON payload with candles/trades/metrics")
    parser.add_argument("--module", help="Run a specific module", default="")
    parser.add_argument("--full", action="store_true", help="Run the full audit stack")
    parser.add_argument("--report", choices=["json", "markdown", "html", "pdf"], default="json")
    parser.add_argument("--outdir", default="reports/strategy_audit")
    args = parser.parse_args(argv)

    payload = _load_json(args.payload)
    context = AuditContext(
        strategy_name=args.strategy,
        strategy_text=args.strategy_text or str(payload.get("strategy_text", "")),
        candles=list(payload.get("candles", [])),
        trades=list(payload.get("trades", [])),
        execution_report=dict(payload.get("execution_report", {})),
        historical_metrics=dict(payload.get("historical_metrics", {})),
        live_metrics=dict(payload.get("live_metrics", {})),
        data_profile=dict(payload.get("data_profile", {})),
        parameter_grid=dict(payload.get("parameter_grid", {})),
        regime_breakdown=dict(payload.get("regime_breakdown", {})),
        notes=dict(payload.get("notes", {})),
    )

    runner = StrategyAuditRunner(output_dir=args.outdir)
    report = runner.run(context)

    if args.report == "json":
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True, default=str))
    else:
        write_reports(report, Path(args.outdir) / args.strategy)
        ext = {"markdown": "audit_report.md", "html": "audit_report.html", "pdf": "audit_report.pdf"}[args.report]
        print(str(Path(args.outdir) / args.strategy / ext))
    return 0 if report.deployment_status not in {"Rejected", "Research"} else 1


if __name__ == "__main__":
    raise SystemExit(main())

