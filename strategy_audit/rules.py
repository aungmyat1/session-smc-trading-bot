from __future__ import annotations


from research.svos.engine import audit_strategy_text

from .module_base import AuditModule
from .models import AuditContext, AuditResult


class RuleAuditModule(AuditModule):
    name = "rule_audit"

    def audit(self, context: AuditContext) -> AuditResult:
        result = audit_strategy_text(context.strategy_text or context.notes.get("strategy_text", ""), strategy_name=context.strategy_name)
        score = 100.0 if result.status == "PASS" else 70.0 if result.status == "FIX" else 0.0
        warnings = [issue.message for issue in result.issues if issue.severity != "CRITICAL"]
        errors = [issue.message for issue in result.issues if issue.severity == "CRITICAL"]
        return AuditResult(
            name=self.name,
            status="PASS" if result.status == "PASS" else "PARTIAL" if result.status == "FIX" else "FAIL",
            score=score,
            warnings=warnings,
            errors=errors,
            metrics={
                "missing_fields": len(result.spec.missing_fields) if result.spec else 0,
                "inferred_fields": len(result.spec.inferred_fields) if result.spec else 0,
            },
            recommendation="Refine the specification before testing" if errors or warnings else "Proceed to data audit",
            details=result.to_dict(),
        )


class SignalAuditModule(AuditModule):
    name = "signal_audit"
    mandatory = False

    def audit(self, context: AuditContext) -> AuditResult:
        signals = context.notes.get("signals", [])
        if not signals:
            return AuditResult(self.name, "NOT_VERIFIED", 0.0, recommendation="Provide signal samples for signal validation")
        missing = [s for s in signals if not isinstance(s, dict) or not s.get("signal_id")]
        score = max(0.0, 100.0 - len(missing) * 20.0)
        return AuditResult(
            name=self.name,
            status="PASS" if not missing else "PARTIAL",
            score=score,
            warnings=[],
            errors=[f"Missing signal_id in {len(missing)} signal samples"] if missing else [],
            metrics={"signal_samples": len(signals), "invalid_signals": len(missing)},
            recommendation="Verify generated signals against expected entries" if missing else "Proceed to execution audit",
        )


class ExecutionAuditModule(AuditModule):
    name = "execution_audit"
    mandatory = True

    def audit(self, context: AuditContext) -> AuditResult:
        report = context.execution_report or {}
        if not report:
            return AuditResult(self.name, "NOT_VERIFIED", 0.0, recommendation="Provide a virtual demo execution report")
        status = str(report.get("status", "")).upper()
        score = float(report.get("final_score", 0.0) or 0.0)
        warnings: list[str] = []
        errors: list[str] = []
        if status != "READY FOR DEMO":
            errors.append(f"Execution status is {status or 'missing'}")
        if not bool(report.get("broker_simulation_passed", False)):
            errors.append("Broker simulation did not pass")
        if not bool(report.get("recovery_passed", False)):
            errors.append("Recovery validation did not pass")
        if not bool(report.get("strategy_version_control_passed", False)):
            errors.append("Strategy version control did not pass")
        return AuditResult(
            name=self.name,
            status="PASS" if not errors and score >= 90 else "PARTIAL" if score >= 70 else "FAIL",
            score=score,
            warnings=warnings,
            errors=errors,
            metrics={
                "slippage_average_pip": report.get("slippage_average_pip", 0.0),
                "slippage_p95_pip": report.get("slippage_p95_pip", 0.0),
                "execution_delay_ms_average": report.get("execution_delay_ms_average", 0.0),
                "execution_delay_ms_maximum": report.get("execution_delay_ms_maximum", 0.0),
            },
            recommendation="Fix execution errors before capital deployment" if errors else "Proceed to risk qualification",
            details=report,
        )

