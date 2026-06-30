from __future__ import annotations

from statistics import mean

from .models import AuditContext, AuditResult
from .module_base import AuditModule


class LatencyAuditModule(AuditModule):
    name = "latency"
    mandatory = False

    def audit(self, context: AuditContext) -> AuditResult:
        report = context.execution_report or {}
        latency = float(report.get("execution_delay_ms_average", 0.0) or 0.0)
        if not report:
            return AuditResult(
                self.name,
                "NOT_VERIFIED",
                0.0,
                recommendation="Provide execution report latency samples",
            )
        score = 100.0 if latency <= 250 else 60.0
        return AuditResult(
            self.name,
            "PASS" if latency <= 250 else "PARTIAL",
            score,
            metrics={
                "avg_latency_ms": latency,
                "max_latency_ms": report.get("execution_delay_ms_maximum", latency),
            },
            recommendation="Keep latency below live tolerances",
        )


class SlippageAuditModule(AuditModule):
    name = "slippage"
    mandatory = True

    def audit(self, context: AuditContext) -> AuditResult:
        report = context.execution_report or {}
        if not report:
            return AuditResult(
                self.name,
                "NOT_VERIFIED",
                0.0,
                recommendation="Provide execution report slippage samples",
            )
        avg = float(report.get("slippage_average_pip", 0.0) or 0.0)
        p95 = float(report.get("slippage_p95_pip", avg) or avg)
        score = 100.0 if avg <= 0.5 and p95 <= 1.0 else 60.0
        return AuditResult(
            self.name,
            "PASS" if score >= 80 else "PARTIAL",
            score,
            metrics={"avg_slippage_pip": avg, "p95_slippage_pip": p95},
            recommendation="Validate broker execution quality",
        )


class SpreadModelAuditModule(AuditModule):
    name = "spread_model"
    mandatory = False

    def audit(self, context: AuditContext) -> AuditResult:
        spreads = [
            float(row.get("spread_pips", 0.0))
            for row in context.notes.get("spread_samples", [])
            if isinstance(row, dict)
        ]
        if not spreads:
            return AuditResult(
                self.name,
                "NOT_VERIFIED",
                0.0,
                recommendation="Provide spread model samples",
            )
        avg = mean(spreads)
        return AuditResult(
            self.name,
            (
                "PASS"
                if avg <= float(context.notes.get("max_spread_pips", 5.0))
                else "PARTIAL"
            ),
            100.0 if avg <= float(context.notes.get("max_spread_pips", 5.0)) else 60.0,
            metrics={"avg_spread_pips": avg},
            recommendation="Use realistic spread assumptions",
        )


class BrokerCompareAuditModule(AuditModule):
    name = "broker_compare"
    mandatory = False

    def audit(self, context: AuditContext) -> AuditResult:
        report = context.execution_report or {}
        if not report:
            return AuditResult(
                self.name,
                "NOT_VERIFIED",
                0.0,
                recommendation="Provide virtual demo execution report",
            )
        if bool(report.get("broker_simulation_passed", False)):
            return AuditResult(
                self.name,
                "PASS",
                100.0,
                metrics={"broker_simulation_passed": True},
                recommendation="Proceed",
            )
        return AuditResult(
            self.name,
            "FAIL",
            0.0,
            errors=["broker simulation did not pass"],
            metrics={"broker_simulation_passed": False},
            recommendation="Fix broker simulation before deployment",
        )


class ExecutionReplayAuditModule(AuditModule):
    name = "execution_replay"
    mandatory = False

    def audit(self, context: AuditContext) -> AuditResult:
        events = context.notes.get("execution_events", [])
        if not events:
            return AuditResult(
                self.name,
                "NOT_VERIFIED",
                0.0,
                recommendation="Provide execution replay events",
            )
        signal_count = sum(
            1
            for ev in events
            if str(ev.get("event_type", "")).upper() == "SIGNAL_CREATED"
        )
        fill_count = sum(
            1
            for ev in events
            if str(ev.get("event_type", "")).upper() == "ORDER_FILLED"
        )
        score = 100.0 if signal_count and fill_count else 60.0
        return AuditResult(
            self.name,
            "PASS" if signal_count and fill_count else "PARTIAL",
            score,
            metrics={"signal_events": signal_count, "fill_events": fill_count},
            recommendation="Cross-check expected versus simulated execution",
        )
