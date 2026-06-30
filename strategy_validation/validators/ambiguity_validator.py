from __future__ import annotations

import re

from ..models import (
    StrategyDocument,
    ValidationFinding,
    ValidationRecommendation,
    ValidatorResult,
    ValidationStatus,
)
from ..module_base import BaseValidator


class AmbiguityValidator(BaseValidator):
    name = "Ambiguity Detection"

    AMBIGUOUS_PHRASES = {
        "strong trend": "Use a directional condition such as EMA50 > EMA200 or HH/HL structure.",
        "good momentum": "Specify an objective momentum threshold such as ATR expansion or candle body ratio.",
        "high probability": "Replace with a tested confluence count or historical win-rate threshold.",
        "large candle": "State a minimum candle body in ATR multiples or pips.",
        "near support": "Define distance in pips or reference a specific prior high/low.",
        "institutional conviction": "Describe the exact displacement, structure, or liquidity criteria.",
        "price looks strong": "Use measurable structure or volatility rules.",
    }

    def validate(self, document: StrategyDocument) -> ValidatorResult:
        text = document.raw_text.lower()
        findings: list[ValidationFinding] = []
        recommendations: list[ValidationRecommendation] = []

        for phrase, replacement in self.AMBIGUOUS_PHRASES.items():
            if re.search(rf"\b{re.escape(phrase)}\b", text):
                findings.append(
                    ValidationFinding(
                        code="ambiguous_phrase",
                        message=f"Subjective wording detected: '{phrase}'.",
                        severity="WARN",
                        evidence=phrase,
                        details={"recommendation": replacement},
                    )
                )
                recommendations.append(
                    ValidationRecommendation(
                        code="replace_ambiguous_phrase",
                        message=f"Replace '{phrase}' with measurable language.",
                        priority="HIGH",
                        original=phrase,
                        improved=replacement,
                        reason="Subjective wording cannot be validated or reproduced reliably.",
                        expected_improvement="Improves objectivity and codability.",
                    )
                )

        score = round(max(0.0, 100.0 - len(findings) * 18.0), 2)
        status: ValidationStatus = (
            "PASS" if not findings else "PARTIAL" if score >= 70 else "FAIL"
        )
        return ValidatorResult(
            validator_name=self.name,
            score=score,
            status=status,
            findings=findings,
            recommendations=recommendations,
            metadata={"ambiguous_phrases": [item.evidence for item in findings]},
        )
