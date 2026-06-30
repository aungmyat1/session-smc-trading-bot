from __future__ import annotations

from ..models import (StrategyDocument, ValidationFinding,
                      ValidationRecommendation, ValidationStatus,
                      ValidatorResult)
from ..module_base import BaseValidator


class InputValidator(BaseValidator):
    name = "Input Validation"

    REQUIRED_FIELDS = {
        "strategy_name": "Strategy name",
        "instrument": "Instrument",
        "market": "Market",
        "timeframe": "Timeframe",
        "session": "Trading session",
        "direction": "Long / Short direction",
        "entry_rules": "Entry rules",
        "exit_rules": "Exit rules",
        "stop_loss": "Stop Loss",
        "take_profit": "Take Profit",
        "risk_model": "Risk model",
        "position_sizing": "Position sizing",
    }

    def validate(self, document: StrategyDocument) -> ValidatorResult:
        missing: list[str] = []
        findings: list[ValidationFinding] = []
        recommendations: list[ValidationRecommendation] = []

        for field_name, label in self.REQUIRED_FIELDS.items():
            if field_name == "strategy_name":
                value = document.strategy_name.strip()
            else:
                value = str(document.extracted_fields.get(field_name, "")).strip()
            if not value:
                missing.append(label)
                findings.append(
                    ValidationFinding(
                        code="missing_field",
                        message=f"Missing required field: {label}",
                        severity="ERROR",
                        location=field_name,
                    )
                )
                recommendations.append(
                    ValidationRecommendation(
                        code="add_required_field",
                        message=f"Document the {label} explicitly.",
                        priority="HIGH",
                        reason="Required for deterministic replay preparation.",
                        expected_improvement="Improves completeness and reduces downstream assumptions.",
                    )
                )

        score = round(
            ((len(self.REQUIRED_FIELDS) - len(missing)) / len(self.REQUIRED_FIELDS))
            * 100.0,
            2,
        )
        status: ValidationStatus = (
            "PASS" if not missing else "PARTIAL" if score >= 60 else "FAIL"
        )
        return ValidatorResult(
            validator_name=self.name,
            score=score,
            status=status,
            findings=findings,
            recommendations=recommendations,
            metadata={"missing_fields": missing, "completeness_score": score},
        )
