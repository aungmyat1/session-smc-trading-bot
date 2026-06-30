from __future__ import annotations

from .module_base import AuditModule
from .models import AuditContext, AuditResult


class RiskMetricsAuditModule(AuditModule):
    name = "risk_metrics"
    mandatory = True

    def audit(self, context: AuditContext) -> AuditResult:
        risk = context.notes.get("risk", {})
        if not risk:
            return AuditResult(
                self.name,
                "NOT_VERIFIED",
                0.0,
                recommendation="Provide risk metrics and limits",
            )
        daily = float(risk.get("daily_dd_pct", 0.0) or 0.0)
        weekly = float(risk.get("weekly_dd_pct", 0.0) or 0.0)
        monthly = float(risk.get("monthly_dd_pct", 0.0) or 0.0)
        heat = float(risk.get("portfolio_heat_pct", 0.0) or 0.0)
        passed = daily < 2.0 and weekly < 5.0 and monthly < 8.0 and heat < 1.0
        score = 100.0 if passed else 40.0
        return AuditResult(
            self.name,
            "PASS" if passed else "FAIL",
            score,
            metrics=risk,
            recommendation=(
                "Reduce exposure before deployment" if not passed else "Proceed"
            ),
        )


class PortfolioAuditModule(AuditModule):
    name = "portfolio"
    mandatory = False

    def audit(self, context: AuditContext) -> AuditResult:
        if not context.notes.get("portfolio"):
            return AuditResult(
                self.name,
                "NOT_VERIFIED",
                0.0,
                recommendation="Provide portfolio-level risk data",
            )
        return AuditResult(
            self.name,
            "PASS",
            100.0,
            metrics=context.notes["portfolio"],
            recommendation="Proceed",
        )


class RiskLimitsAuditModule(AuditModule):
    name = "risk_limits"
    mandatory = False

    def audit(self, context: AuditContext) -> AuditResult:
        limits = context.notes.get("risk_limits", {})
        if not limits:
            return AuditResult(
                self.name,
                "NOT_VERIFIED",
                0.0,
                recommendation="Provide configured risk limits",
            )
        return AuditResult(
            self.name, "PASS", 100.0, metrics=limits, recommendation="Proceed"
        )


class DrawdownAuditModule(AuditModule):
    name = "drawdown"
    mandatory = True

    def audit(self, context: AuditContext) -> AuditResult:
        dd = context.historical_metrics.get("max_drawdown") or context.notes.get(
            "max_drawdown"
        )
        if dd is None:
            return AuditResult(
                self.name,
                "NOT_VERIFIED",
                0.0,
                recommendation="Provide drawdown evidence",
            )
        dd = float(dd)
        return AuditResult(
            self.name,
            "PASS" if dd <= 10.0 else "FAIL",
            100.0 if dd <= 10.0 else 0.0,
            metrics={"max_drawdown": dd},
            recommendation="Keep drawdown within institutional limits",
        )


class CapitalAllocationAuditModule(AuditModule):
    name = "capital_allocation"
    mandatory = False

    def audit(self, context: AuditContext) -> AuditResult:
        allocation = context.notes.get("capital_allocation", {})
        if not allocation:
            return AuditResult(
                self.name,
                "NOT_VERIFIED",
                0.0,
                recommendation="Provide capital allocation plan",
            )
        return AuditResult(
            self.name, "PASS", 100.0, metrics=allocation, recommendation="Proceed"
        )
