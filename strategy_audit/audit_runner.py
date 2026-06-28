from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from research.validation.engine import load_validation_config

from .audit_engine import StrategyAuditEngine
from .models import AuditContext, AuditReport
from .report_builder import write_reports


class StrategyAuditRunner:
    def __init__(self, engine: StrategyAuditEngine | None = None, output_dir: Path | str | None = None) -> None:
        self.engine = engine or StrategyAuditEngine()
        self.output_dir = Path(output_dir) if output_dir is not None else Path("reports/strategy_audit")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.validation_config = load_validation_config()

    def run(self, context: AuditContext) -> AuditReport:
        report = self.engine.audit(context)
        write_reports(report, self.output_dir / context.strategy_name)
        return report

    def from_payload(self, payload: dict[str, Any]) -> AuditReport:
        context = AuditContext(
            strategy_name=str(payload.get("strategy_name", payload.get("strategy", "UNKNOWN"))),
            strategy_text=str(payload.get("strategy_text", "")),
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
        if not context.strategy_text and payload.get("strategy_text_source"):
            text_path = Path(str(payload["strategy_text_source"]))
            if text_path.exists():
                context.strategy_text = text_path.read_text(encoding="utf-8")
        return self.run(context)
