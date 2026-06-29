from __future__ import annotations

import re

from ..models import StrategyDocument, ValidationFinding, ValidationRecommendation, ValidatorResult
from ..module_base import BaseValidator


class InstitutionalRuleValidator(BaseValidator):
    name = "Institutional Rule Validation"

    SUPPORTED_CONCEPTS = (
        "market structure",
        "bos",
        "choch",
        "liquidity sweep",
        "order block",
        "fair value gap",
        "premium",
        "discount",
        "session filter",
    )

    VAGUE_CONCEPTS = {
        "wait for liquidity": "State which liquidity pool is swept and by how much.",
        "order block": "Define the candle selection and invalidation rule for the order block.",
        "fair value gap": "Specify the exact three-candle gap condition and minimum size.",
    }

    def validate(self, document: StrategyDocument) -> ValidatorResult:
        text = document.raw_text.lower()
        findings: list[ValidationFinding] = []
        recommendations: list[ValidationRecommendation] = []
        detected = [concept for concept in self.SUPPORTED_CONCEPTS if concept in text]

        for phrase, improvement in self.VAGUE_CONCEPTS.items():
            if phrase in text and not re.search(r"(>=|<=|>|<|\d)", phrase):
                findings.append(
                    ValidationFinding(
                        code="undefined_institutional_concept",
                        message=f"Institutional concept is mentioned without enough definition: '{phrase}'.",
                        severity="WARN",
                        evidence=phrase,
                    )
                )
                recommendations.append(
                    ValidationRecommendation(
                        code="define_institutional_concept",
                        message=f"Define '{phrase}' in measurable terms.",
                        priority="HIGH",
                        original=phrase,
                        improved=improvement,
                        reason="Institutional concepts must be explicit before replay.",
                        expected_improvement="Improves domain clarity and codability.",
                    )
                )

        if not detected:
            findings.append(
                ValidationFinding(
                    code="missing_institutional_context",
                    message="No supported institutional concepts were explicitly defined.",
                    severity="WARN",
                )
            )

        score = round(min(100.0, len(detected) * 12.0 + 20.0 - len(findings) * 15.0), 2)
        score = max(score, 0.0)
        status = "PASS" if detected and not findings and score >= 80 else "PARTIAL" if score >= 60 else "FAIL"
        return ValidatorResult(
            validator_name=self.name,
            score=score,
            status=status,
            findings=findings,
            recommendations=recommendations,
            metadata={"detected_concepts": detected, "institutional_quality_score": score},
        )
