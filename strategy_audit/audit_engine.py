from __future__ import annotations

from typing import Iterable

from research.lineage import build_release_metadata

from .data import IntegrityAuditModule
from .deployment_gate import DeploymentGate
from .monitoring import StrategyDriftAuditModule
from .models import AuditContext, AuditReport, AuditResult
from .regime import RegimeAuditModule
from .risk import RiskMetricsAuditModule
from .robustness import ParameterStabilityAuditModule
from .rules import ExecutionAuditModule, RuleAuditModule
from .statistics import (
    MonteCarloAuditModule,
    PerformanceAuditModule,
    WalkForwardAuditModule,
)

DEFAULT_MODULES = [
    RuleAuditModule(),
    IntegrityAuditModule(),
    PerformanceAuditModule(),
    RegimeAuditModule(),
    ParameterStabilityAuditModule(),
    WalkForwardAuditModule(),
    MonteCarloAuditModule(),
    ExecutionAuditModule(),
    RiskMetricsAuditModule(),
    StrategyDriftAuditModule(),
]


class StrategyAuditEngine:
    def __init__(
        self, modules: Iterable | None = None, gate: DeploymentGate | None = None
    ) -> None:
        self.modules = list(modules or DEFAULT_MODULES)
        self.gate = gate or DeploymentGate()

    def audit(self, context: AuditContext) -> AuditReport:
        module_results: list[AuditResult] = []
        for module in self.modules:
            module_results.append(module.audit(context))
        readiness_score = self._readiness_score(module_results)
        overall_status = self._overall_status(module_results)
        gate = self.gate.decide(
            AuditReport(
                strategy=context.strategy_name,
                module_results=module_results,
                overall_status=overall_status,
                readiness_score=readiness_score,
                deployment_status=self._deployment_level(
                    module_results, readiness_score
                ),
                capital_tier=self._capital_tier(readiness_score),
                recommended_risk_pct=self._recommended_risk_pct(readiness_score),
                expected_pf=self._expected_pf(context, module_results),
                expected_win_rate=self._expected_win_rate(context, module_results),
                expected_monthly_dd=self._expected_monthly_dd(context, module_results),
                confidence=self._confidence(module_results),
                summary="",
                risk_assessment={
                    "max_drawdown": context.historical_metrics.get("max_drawdown"),
                    "risk": context.notes.get("risk", {}),
                },
                failure_modes=[],
                recommendations=[],
                release=build_release_metadata(),
            )
        )
        report = AuditReport(
            strategy=context.strategy_name,
            module_results=module_results,
            overall_status=overall_status if not gate.rationale else "FAIL",
            readiness_score=readiness_score,
            deployment_status=(
                gate.deployment_level if not gate.rationale else gate.status
            ),
            capital_tier=self._capital_tier(
                readiness_score if not gate.rationale else min(readiness_score, 49.9)
            ),
            recommended_risk_pct=self._recommended_risk_pct(readiness_score),
            expected_pf=self._expected_pf(context, module_results),
            expected_win_rate=self._expected_win_rate(context, module_results),
            expected_monthly_dd=self._expected_monthly_dd(context, module_results),
            confidence=self._confidence(module_results),
            summary=self._summary(module_results, readiness_score, gate.rationale),
            risk_assessment={
                "max_drawdown": context.historical_metrics.get("max_drawdown"),
                "risk": context.notes.get("risk", {}),
            },
            failure_modes=self._failure_modes(module_results),
            recommendations=self._recommendations(module_results, gate.rationale),
            release=build_release_metadata(),
        )
        return report

    def _readiness_score(self, results: list[AuditResult]) -> float:
        if not results:
            return 0.0
        weights = [
            (
                1.2
                if item.name
                in {
                    "rule_audit",
                    "data_audit",
                    "execution_audit",
                    "risk_metrics",
                    "strategy_drift",
                }
                else 1.0
            )
            for item in results
        ]
        weighted = sum(r.score * w for r, w in zip(results, weights))
        return round(weighted / sum(weights), 2)

    def _overall_status(self, results: list[AuditResult]) -> str:
        if any(r.status == "FAIL" for r in results):
            return "FAIL"
        if any(r.status in {"PARTIAL", "NOT_VERIFIED"} for r in results):
            return "PARTIAL"
        return "PASS"

    def _deployment_level(
        self, results: list[AuditResult], readiness_score: float
    ) -> str:
        if readiness_score < 50:
            return "Rejected"
        if readiness_score < 65:
            return "Research"
        if readiness_score < 75:
            return "Backtest"
        if readiness_score < 82:
            return "Replay"
        if readiness_score < 88:
            return "Demo"
        if readiness_score < 94:
            return "Pilot Live"
        return "Production"

    def _capital_tier(self, readiness_score: float) -> str:
        if readiness_score < 70:
            return "Research"
        if readiness_score < 85:
            return "Demo"
        if readiness_score < 95:
            return "Pilot Live"
        return "Production"

    def _recommended_risk_pct(self, readiness_score: float) -> float:
        if readiness_score < 70:
            return 0.10
        if readiness_score < 85:
            return 0.30
        if readiness_score < 95:
            return 0.50
        return 1.00

    def _expected_pf(
        self, context: AuditContext, results: list[AuditResult]
    ) -> float | None:
        if context.historical_metrics.get("profit_factor") is not None:
            return float(context.historical_metrics["profit_factor"])
        for result in results:
            if "profit_factor" in result.metrics:
                return float(result.metrics["profit_factor"])
        return None

    def _expected_win_rate(
        self, context: AuditContext, results: list[AuditResult]
    ) -> float | None:
        if context.historical_metrics.get("win_rate") is not None:
            return float(context.historical_metrics["win_rate"])
        for result in results:
            if "win_rate" in result.metrics:
                return float(result.metrics["win_rate"])
        return None

    def _expected_monthly_dd(
        self, context: AuditContext, results: list[AuditResult]
    ) -> float | None:
        if context.historical_metrics.get("max_drawdown") is not None:
            return float(context.historical_metrics["max_drawdown"])
        for result in results:
            if "max_drawdown" in result.metrics:
                return float(result.metrics["max_drawdown"])
        return None

    def _confidence(self, results: list[AuditResult]) -> float:
        if not results:
            return 0.0
        verified = sum(1 for r in results if r.status == "PASS")
        return round(verified / len(results) * 100.0, 2)

    def _summary(
        self, results: list[AuditResult], readiness_score: float, rationale: list[str]
    ) -> str:
        if rationale:
            return "Deployment rejected: " + "; ".join(rationale)
        return f"Readiness score {readiness_score:.1f}% with {sum(1 for r in results if r.status == 'PASS')} passing modules."

    def _failure_modes(self, results: list[AuditResult]) -> list[str]:
        failures = []
        for result in results:
            failures.extend(result.errors)
        return failures

    def _recommendations(
        self, results: list[AuditResult], rationale: list[str]
    ) -> list[str]:
        recs = [item.recommendation for item in results if item.recommendation]
        recs.extend(rationale)
        return [item for item in dict.fromkeys(recs) if item]
