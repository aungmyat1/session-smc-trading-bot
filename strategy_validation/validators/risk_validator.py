from __future__ import annotations

from ..models import (
    StrategyDocument,
    ValidationFinding,
    ValidationRecommendation,
    ValidatorResult,
    ValidationStatus,
)
from ..module_base import BaseValidator


class RiskValidationValidator(BaseValidator):
    name = "Risk Management Validation"

    CONTROLS = {
        "stop_loss": "Stop Loss",
        "take_profit": "Take Profit",
        "risk_model": "Risk %",
        "max_daily_loss": "Maximum Daily Loss",
        "max_drawdown": "Maximum Drawdown",
        "max_open_positions": "Maximum Open Positions",
        "news_rules": "News Rules",
        "position_sizing": "Position Sizing",
    }

    def validate(self, document: StrategyDocument) -> ValidatorResult:
        findings: list[ValidationFinding] = []
        recommendations: list[ValidationRecommendation] = []
        missing_controls: list[str] = []

        for field_name, label in self.CONTROLS.items():
            value = str(document.extracted_fields.get(field_name, "")).strip()
            if not value:
                missing_controls.append(label)
                findings.append(
                    ValidationFinding(
                        code="missing_risk_control",
                        message=f"Missing risk control: {label}",
                        severity=(
                            "ERROR"
                            if label
                            in {"Stop Loss", "Take Profit", "Risk %", "Position Sizing"}
                            else "WARN"
                        ),
                        location=field_name,
                    )
                )
                recommendations.append(
                    ValidationRecommendation(
                        code="add_risk_control",
                        message=f"Add an explicit {label} rule.",
                        priority="HIGH",
                        reason="Risk controls must be documented before replay approval.",
                        expected_improvement="Improves capital protection and operational readiness.",
                    )
                )

        score = round(
            ((len(self.CONTROLS) - len(missing_controls)) / len(self.CONTROLS)) * 100.0,
            2,
        )
        status: ValidationStatus = (
            "PASS" if not missing_controls else "PARTIAL" if score >= 62.5 else "FAIL"
        )
        return ValidatorResult(
            validator_name=self.name,
            score=score,
            status=status,
            findings=findings,
            recommendations=recommendations,
            metadata={"missing_controls": missing_controls, "risk_score": score},
        )
