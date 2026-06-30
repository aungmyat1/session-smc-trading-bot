from __future__ import annotations

from dataclasses import dataclass

from .models import AuditReport


@dataclass
class DeploymentDecision:
    status: str
    deployment_level: str
    capital_tier: str
    rationale: list[str]


class DeploymentGate:
    def __init__(
        self,
        minimum_scores: dict[str, float] | None = None,
        minimum_readiness: float = 80.0,
    ) -> None:
        self.minimum_scores = minimum_scores or {
            "rule_audit": 80,
            "data_audit": 80,
            "performance": 70,
            "regime_audit": 70,
            "parameter_stability": 70,
            "walk_forward": 70,
            "monte_carlo": 70,
            "execution_audit": 80,
            "risk_metrics": 90,
            "strategy_drift": 70,
        }
        self.minimum_readiness = minimum_readiness

    def decide(self, report: AuditReport) -> DeploymentDecision:
        rationale: list[str] = []
        score_map = {result.name: result.score for result in report.module_results}
        for name, minimum in self.minimum_scores.items():
            if name in score_map and score_map[name] < minimum:
                rationale.append(
                    f"{name} below minimum: {score_map[name]:.1f} < {minimum:.1f}"
                )
        if report.readiness_score < self.minimum_readiness:
            rationale.append(
                f"readiness below minimum: {report.readiness_score:.1f} < {self.minimum_readiness:.1f}"
            )
        if rationale:
            return DeploymentDecision("REJECTED", "Research", "Research", rationale)
        if report.deployment_status == "Production":
            return DeploymentDecision(
                "APPROVED", "Production", report.capital_tier, rationale
            )
        return DeploymentDecision(
            "APPROVED", report.deployment_status, report.capital_tier, rationale
        )
