from __future__ import annotations

from ..models import StrategyDocument, ValidationFinding, ValidationRecommendation, ValidatorResult, ValidationStatus
from ..module_base import BaseValidator


class TestabilityValidator(BaseValidator):
    name = "Testability Validation"

    def validate(self, document: StrategyDocument) -> ValidatorResult:
        text = document.raw_text.lower()
        findings: list[ValidationFinding] = []
        recommendations: list[ValidationRecommendation] = []

        if "entry" not in text:
            findings.append(
                ValidationFinding(
                    code="entry_not_identifiable",
                    message="The specification does not clearly identify entry conditions.",
                    severity="ERROR",
                )
            )
        if "exit" not in text and "take profit" not in text:
            findings.append(
                ValidationFinding(
                    code="exit_not_identifiable",
                    message="The specification does not clearly identify exit conditions.",
                    severity="ERROR",
                )
            )
        if not any(token in text for token in (">", "<", "at least", "minimum", "maximum", "within", "exactly")):
            findings.append(
                ValidationFinding(
                    code="coding_requires_assumptions",
                    message="Rules appear too qualitative to code without assumptions.",
                    severity="WARN",
                )
            )
        if any(phrase in text for phrase in ("strong trend", "good momentum", "high probability", "large candle", "near support")):
            findings.append(
                ValidationFinding(
                    code="reviewers_may_disagree",
                    message="Subjective language makes identical trade selection unlikely.",
                    severity="WARN",
                )
            )

        for finding in findings:
            recommendations.append(
                ValidationRecommendation(
                    code="improve_testability",
                    message=f"Address testability issue: {finding.message}",
                    priority="HIGH" if finding.severity == "ERROR" else "MEDIUM",
                    reason="Replay requires that reviewers and code identify the same trades.",
                    expected_improvement="Improves consistency across manual and automated review.",
                )
            )

        score = round(max(0.0, 100.0 - sum(30 if item.severity == "ERROR" else 15 for item in findings)), 2)
        status: ValidationStatus = "PASS" if not findings else "PARTIAL" if score >= 70 else "FAIL"
        return ValidatorResult(
            validator_name=self.name,
            score=score,
            status=status,
            findings=findings,
            recommendations=recommendations,
            metadata={"testability_score": score},
        )
