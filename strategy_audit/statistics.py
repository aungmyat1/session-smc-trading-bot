from __future__ import annotations

from statistics import mean

from research.robustness import (monte_carlo_resampling, parameter_sensitivity,
                                 walk_forward_analysis)

from ._helpers import (_expectancy, _max_drawdown, _numbers, _profit_factor,
                       _sharpe, _sortino)
from .models import AuditContext, AuditResult
from .module_base import AuditModule


def _returns(context: AuditContext) -> list[float]:
    if context.trades:
        values = [
            row.get("std_net_r", row.get("net_r", row.get("r", 0.0)))
            for row in context.trades
            if isinstance(row, dict)
        ]
        nums = _numbers(values)
        if nums:
            return nums
    return _numbers(context.notes.get("returns", []))


class PerformanceAuditModule(AuditModule):
    name = "performance"

    def audit(self, context: AuditContext) -> AuditResult:
        returns = _returns(context)
        if not returns:
            return AuditResult(
                self.name,
                "NOT_VERIFIED",
                0.0,
                recommendation="Provide trade return series or backtest metrics",
            )
        pf = _profit_factor(returns)
        expectancy = _expectancy(returns)
        score = min(100.0, max(0.0, 50.0 + expectancy * 40.0 + (pf - 1.0) * 20.0))
        return AuditResult(
            self.name,
            "PASS" if score >= 80 else "PARTIAL",
            score,
            metrics={
                "profit_factor": pf,
                "expectancy": expectancy,
                "average_rr": mean(abs(v) for v in returns) if returns else 0.0,
                "sharpe": _sharpe(returns),
                "sortino": _sortino(returns),
                "max_drawdown": _max_drawdown(returns),
            },
            recommendation=(
                "Proceed to regime audit"
                if score >= 80
                else "Improve edge before promotion"
            ),
        )


class ExpectancyAuditModule(AuditModule):
    name = "expectancy"
    mandatory = False

    def audit(self, context: AuditContext) -> AuditResult:
        returns = _returns(context)
        if not returns:
            return AuditResult(
                self.name, "NOT_VERIFIED", 0.0, recommendation="Provide trade returns"
            )
        expectancy = _expectancy(returns)
        return AuditResult(
            self.name,
            "PASS" if expectancy > 0 else "FAIL",
            min(100.0, max(0.0, 50.0 + expectancy * 50.0)),
            metrics={"expectancy": expectancy},
            recommendation="Review setup quality" if expectancy <= 0 else "Proceed",
        )


class MonteCarloAuditModule(AuditModule):
    name = "monte_carlo"
    mandatory = False

    def audit(self, context: AuditContext) -> AuditResult:
        trades = context.trades
        if not trades:
            return AuditResult(
                self.name,
                "NOT_VERIFIED",
                0.0,
                recommendation="Provide trade rows for Monte Carlo",
            )
        payload = monte_carlo_resampling(
            trades, iterations=int(context.notes.get("monte_carlo_iterations", 500))
        )
        score = 100.0 if payload.get("passed") else 50.0
        return AuditResult(
            self.name,
            "PASS" if payload.get("passed") else "PARTIAL",
            score,
            metrics=payload,
            recommendation="Validate the distribution of outcomes",
        )


class WalkForwardAuditModule(AuditModule):
    name = "walk_forward"
    mandatory = False

    def audit(self, context: AuditContext) -> AuditResult:
        trades = context.trades
        if not trades:
            return AuditResult(
                self.name,
                "NOT_VERIFIED",
                0.0,
                recommendation="Provide trade rows for walk-forward",
            )
        payload = walk_forward_analysis(
            trades, folds=int(context.notes.get("walk_forward_folds", 4))
        )
        return AuditResult(
            self.name,
            "PASS" if payload.get("passed") else "PARTIAL",
            100.0 if payload.get("passed") else 55.0,
            metrics=payload,
            recommendation="Check window consistency",
        )


class BootstrapAuditModule(AuditModule):
    name = "bootstrap"
    mandatory = False

    def audit(self, context: AuditContext) -> AuditResult:
        returns = _returns(context)
        if len(returns) < 5:
            return AuditResult(
                self.name,
                "NOT_VERIFIED",
                0.0,
                recommendation="Provide at least five trade returns",
            )
        n = len(returns)
        samples = [mean(returns[i::2]) for i in range(2)] if n >= 2 else returns
        score = 100.0 if samples and mean(samples) > 0 else 60.0
        return AuditResult(
            self.name,
            "PASS" if score >= 80 else "PARTIAL",
            score,
            metrics={
                "sample_mean": mean(samples) if samples else 0.0,
                "sample_count": n,
            },
            recommendation="Use bootstrap confidence intervals for robustness",
        )


class StabilityAuditModule(AuditModule):
    name = "stability"
    mandatory = False

    def audit(self, context: AuditContext) -> AuditResult:
        parameter_grid = context.parameter_grid or {}
        payload = (
            parameter_sensitivity(parameter_grid)
            if parameter_grid
            else {"passed": False, "reason": "no_parameter_grid"}
        )
        if not parameter_grid:
            return AuditResult(
                self.name,
                "NOT_VERIFIED",
                0.0,
                recommendation="Provide parameter grid results",
            )
        return AuditResult(
            self.name,
            "PASS" if payload.get("passed") else "PARTIAL",
            100.0 if payload.get("passed") else 55.0,
            metrics=payload,
            recommendation="Prefer stable plateaus over fragile peaks",
        )


class DistributionAuditModule(AuditModule):
    name = "distribution"
    mandatory = False

    def audit(self, context: AuditContext) -> AuditResult:
        returns = _returns(context)
        if len(returns) < 3:
            return AuditResult(
                self.name,
                "NOT_VERIFIED",
                0.0,
                recommendation="Provide more trade returns",
            )
        avg = mean(returns)
        score = 100.0 if avg > 0 else 45.0
        return AuditResult(
            self.name,
            "PASS" if avg > 0 else "PARTIAL",
            score,
            metrics={"average": avg},
            recommendation="Review skew and kurtosis before deployment",
        )
