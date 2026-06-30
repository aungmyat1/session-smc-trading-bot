from __future__ import annotations

from ..models import (StrategyDocument, ValidationFinding,
                      ValidationRecommendation, ValidationStatus,
                      ValidatorResult)
from ..module_base import BaseValidator


class RuleCompletenessValidator(BaseValidator):
    name = "Rule Completeness Validation"

    QUESTIONS = {
        "when": ("session", "time", "killzone", "bar", "window"),
        "where": ("level", "range", "high", "low", "zone", "order block", "fvg"),
        "why": ("because", "bias", "confirmation", "reason", "philosophy"),
        "how": ("entry", "trigger", "body", "close", "atr", "condition"),
        "exit": ("take profit", "stop loss", "exit", "tp", "sl"),
        "cancel": ("cancel", "invalidate", "reject", "skip", "timeout"),
    }

    def validate(self, document: StrategyDocument) -> ValidatorResult:
        rule_text = "\n".join(
            filter(
                None,
                [
                    document.sections.get(
                        "Signal Chain (phase-by-phase, in execution order)", ""
                    ),
                    document.extracted_fields.get("entry_rules", ""),
                    document.extracted_fields.get("exit_rules", ""),
                    document.sections.get("Confirmation Rules", ""),
                ],
            )
        ).lower()
        findings: list[ValidationFinding] = []
        recommendations: list[ValidationRecommendation] = []
        missing_dimensions: list[str] = []

        for dimension, hints in self.QUESTIONS.items():
            if not any(hint in rule_text for hint in hints):
                missing_dimensions.append(dimension)
                findings.append(
                    ValidationFinding(
                        code="incomplete_rule_dimension",
                        message=f"Trading rules do not clearly answer '{dimension}'.",
                        severity="ERROR" if dimension in {"how", "exit"} else "WARN",
                        location=dimension,
                    )
                )
                recommendations.append(
                    ValidationRecommendation(
                        code="complete_rule_dimension",
                        message=f"Add explicit '{dimension}' criteria to the entry/exit flow.",
                        priority="HIGH" if dimension in {"how", "exit"} else "MEDIUM",
                        reason="Each strategy rule should answer when, where, why, how, exit, and cancel.",
                        expected_improvement="Improves rule completeness and reviewer alignment.",
                    )
                )

        score = round(
            ((len(self.QUESTIONS) - len(missing_dimensions)) / len(self.QUESTIONS))
            * 100.0,
            2,
        )
        status: ValidationStatus = (
            "PASS" if not missing_dimensions else "PARTIAL" if score >= 66 else "FAIL"
        )
        return ValidatorResult(
            validator_name=self.name,
            score=score,
            status=status,
            findings=findings,
            recommendations=recommendations,
            metadata={
                "missing_dimensions": missing_dimensions,
                "rule_completeness_score": score,
            },
        )
