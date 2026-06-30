from __future__ import annotations

from dataclasses import asdict, dataclass, field

from ..models import StrategyDocument, ValidationRecommendation
from .question_engine import ClarificationQuestion, ClarificationQuestionEngine


@dataclass(frozen=True)
class EnhancementPlan:
    strategy_name: str
    summary: str
    status: str
    questions: list[ClarificationQuestion] = field(default_factory=list)
    revised_rule_snippets: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["questions"] = [item.to_dict() for item in self.questions]
        return payload


class StrategyEditorEngine:
    """Build a deterministic enhancement plan from audit findings."""

    def __init__(
        self, question_engine: ClarificationQuestionEngine | None = None
    ) -> None:
        self.question_engine = question_engine or ClarificationQuestionEngine()

    def build_plan(
        self,
        document: StrategyDocument,
        recommendations: list[ValidationRecommendation],
        readiness_decision: str,
    ) -> EnhancementPlan:
        questions = self.question_engine.build_questions(document, recommendations)
        revised = [
            item.proposed_revision for item in questions if item.proposed_revision
        ]
        recommendation_text = [item.message for item in recommendations if item.message]
        if questions:
            summary = f"Generated {len(questions)} clarification questions and {len(revised)} rewrite snippets."
            status = (
                "ACTION_REQUIRED"
                if readiness_decision != "READY_FOR_REPLAY"
                else "READY_WITH_SUGGESTIONS"
            )
        else:
            summary = "No further clarification prompts were required."
            status = "READY"
        return EnhancementPlan(
            strategy_name=document.strategy_name,
            summary=summary,
            status=status,
            questions=questions,
            revised_rule_snippets=revised,
            recommendations=recommendation_text,
        )
