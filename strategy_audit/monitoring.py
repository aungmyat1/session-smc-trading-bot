from __future__ import annotations

from .module_base import AuditModule
from .models import AuditContext, AuditResult


class StrategyDriftAuditModule(AuditModule):
    name = "strategy_drift"
    mandatory = True

    def audit(self, context: AuditContext) -> AuditResult:
        historical = context.historical_metrics or {}
        live = context.live_metrics or {}
        if not historical or not live:
            return AuditResult(self.name, "NOT_VERIFIED", 0.0, recommendation="Provide live and historical metrics")
        warnings: list[str] = []
        drift = {}
        for key in ("profit_factor", "win_rate", "expectancy", "trade_count", "max_drawdown"):
            if key not in historical or key not in live:
                continue
            h = float(historical[key])
            l = float(live[key])
            delta = abs(l - h)
            delta_pct = 0.0 if h == 0 else abs(delta / h)
            drift[key] = {"historical": h, "live": l, "delta_pct": delta_pct}
            if delta_pct > float(context.notes.get("drift_threshold_pct", 0.20)):
                warnings.append(f"{key} drift {delta_pct:.2%}")
        status = "PASS" if not warnings else "PARTIAL"
        score = 100.0 if not warnings else max(50.0, 100.0 - len(warnings) * 10.0)
        return AuditResult(self.name, status, score, warnings=warnings, metrics=drift, recommendation="Investigate production drift" if warnings else "Proceed")


class ProductionMonitorAuditModule(AuditModule):
    name = "production_monitor"
    mandatory = False

    def audit(self, context: AuditContext) -> AuditResult:
        if not context.notes.get("monitoring"):
            return AuditResult(self.name, "NOT_VERIFIED", 0.0, recommendation="Provide monitoring evidence")
        return AuditResult(self.name, "PASS", 100.0, metrics=context.notes["monitoring"], recommendation="Proceed")


class AlertEngineAuditModule(AuditModule):
    name = "alert_engine"
    mandatory = False

    def audit(self, context: AuditContext) -> AuditResult:
        alerts = context.notes.get("alerts", [])
        if not alerts:
            return AuditResult(self.name, "NOT_VERIFIED", 0.0, recommendation="Provide alerting configuration")
        return AuditResult(self.name, "PASS", 100.0, metrics={"alert_count": len(alerts)}, recommendation="Proceed")


class HealthChecksAuditModule(AuditModule):
    name = "health_checks"
    mandatory = False

    def audit(self, context: AuditContext) -> AuditResult:
        checks = context.notes.get("health_checks", {})
        if not checks:
            return AuditResult(self.name, "NOT_VERIFIED", 0.0, recommendation="Provide health-check results")
        failed = [k for k, v in checks.items() if not bool(v)]
        return AuditResult(self.name, "PASS" if not failed else "PARTIAL", 100.0 if not failed else 60.0, metrics=checks, recommendation="Fix failed health checks before deployment")

