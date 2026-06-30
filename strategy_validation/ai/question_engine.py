from __future__ import annotations

from dataclasses import asdict, dataclass, field

from ..models import StrategyDocument, ValidationRecommendation


@dataclass(frozen=True)
class ClarificationOption:
    label: str
    description: str
    value: str = ""

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class ClarificationQuestion:
    code: str
    prompt: str
    context: str = ""
    blocking: bool = True
    options: list[ClarificationOption] = field(default_factory=list)
    recommended_answer: str = ""
    proposed_revision: str = ""
    reason: str = ""

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["options"] = [item.to_dict() for item in self.options]
        return payload


class ClarificationQuestionEngine:
    """Deterministic generator for enhancement-stage rule-resolution prompts."""

    def build_questions(
        self,
        document: StrategyDocument,
        recommendations: list[ValidationRecommendation],
    ) -> list[ClarificationQuestion]:
        questions: list[ClarificationQuestion] = []
        questions.extend(self._from_recommendations(recommendations))
        text = document.raw_text.lower()
        questions.extend(self._bos_question(text))
        questions.extend(self._choch_question(text))
        questions.extend(self._fvg_question(text))
        questions.extend(self._order_block_question(text))
        questions.extend(self._sweep_timeout_question(text))
        questions.extend(self._cancellation_question(text))

        deduped: list[ClarificationQuestion] = []
        seen: set[tuple[str, str]] = set()
        for item in questions:
            key = (item.code, item.prompt)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
        return deduped

    def _from_recommendations(
        self, recommendations: list[ValidationRecommendation]
    ) -> list[ClarificationQuestion]:
        questions: list[ClarificationQuestion] = []
        for item in recommendations:
            prompt = item.message.strip().rstrip(".")
            if not prompt:
                continue
            if item.original:
                prompt = f"How should this rule be defined explicitly: {item.original}?"
            elif prompt.lower().startswith("document the "):
                prompt = f"What is the explicit {prompt[13:].lower()}?"
            elif prompt.lower().startswith("add an explicit "):
                prompt = f"What is the explicit {prompt[16:].lower()}?"
            else:
                prompt = prompt + "?"
            questions.append(
                ClarificationQuestion(
                    code=item.code,
                    prompt=prompt,
                    context=item.original,
                    blocking=item.priority == "HIGH",
                    recommended_answer=item.improved or item.message,
                    proposed_revision=item.improved or item.message,
                    reason=item.reason,
                    options=[],
                )
            )
        return questions

    def _bos_question(self, text: str) -> list[ClarificationQuestion]:
        if (
            "bos" not in text
            or "close beyond" in text
            or "close >" in text
            or "close <" in text
        ):
            return []
        return [
            ClarificationQuestion(
                code="bos_definition",
                prompt="Should BOS require a candle close beyond the reference level?",
                context="BOS appears in the rulebook without an explicit break condition.",
                options=[
                    ClarificationOption(
                        "Close beyond level (Recommended)",
                        "Most reproducible institutional definition.",
                        "close_beyond",
                    ),
                    ClarificationOption(
                        "Wick through level",
                        "More permissive and more subjective.",
                        "wick_through",
                    ),
                    ClarificationOption(
                        "Either close or wick", "Least deterministic option.", "either"
                    ),
                ],
                recommended_answer="Close beyond level",
                proposed_revision="BOS is valid only when a candle closes beyond the reference swing level.",
                reason="Replay and coding require one deterministic BOS trigger.",
            )
        ]

    def _choch_question(self, text: str) -> list[ClarificationQuestion]:
        if "choch" not in text or any(
            token in text
            for token in ("within ", "next candle", "first candle", "within 3 candles")
        ):
            return []
        return [
            ClarificationQuestion(
                code="choch_timing",
                prompt="How long after the sweep does CHOCH remain valid?",
                context="CHOCH is mentioned without a timing window.",
                options=[
                    ClarificationOption(
                        "Within 3 candles (Recommended)",
                        "Short confirmation window keeps setup deterministic.",
                        "3_candles",
                    ),
                    ClarificationOption(
                        "Within 5 candles", "Allows slower reversals.", "5_candles"
                    ),
                    ClarificationOption(
                        "Until session ends",
                        "Broadest but least strict.",
                        "session_end",
                    ),
                ],
                recommended_answer="Within 3 candles",
                proposed_revision="CHOCH must occur within 3 candles after the sweep or the setup is cancelled.",
                reason="Timing windows prevent unlimited setup validity.",
            )
        ]

    def _fvg_question(self, text: str) -> list[ClarificationQuestion]:
        if "fvg" not in text or any(
            token in text
            for token in ("until mitigated", "5 candles", "valid after", "three-candle")
        ):
            return []
        return [
            ClarificationQuestion(
                code="fvg_validity",
                prompt="How long does an FVG remain valid for entry confirmation?",
                context="FVG is present without a validity window.",
                options=[
                    ClarificationOption(
                        "Until mitigated (Recommended)",
                        "Common institutional definition.",
                        "until_mitigated",
                    ),
                    ClarificationOption(
                        "Maximum 5 candles", "Adds a time-based expiry.", "5_candles"
                    ),
                    ClarificationOption(
                        "Same session only",
                        "Expires at session boundary.",
                        "same_session",
                    ),
                ],
                recommended_answer="Until mitigated",
                proposed_revision="The FVG remains valid until mitigated or until the session ends, whichever comes first.",
                reason="A validity rule is needed to prevent stale setups.",
            )
        ]

    def _order_block_question(self, text: str) -> list[ClarificationQuestion]:
        if "order block" not in text or any(
            token in text
            for token in (
                "last bullish candle",
                "last bearish candle",
                "engulfing",
                "mitigation",
            )
        ):
            return []
        return [
            ClarificationQuestion(
                code="order_block_definition",
                prompt="Which candle defines the order block used by the setup?",
                context="Order block is referenced without a deterministic candle-selection rule.",
                options=[
                    ClarificationOption(
                        "Last opposing candle before displacement (Recommended)",
                        "Most codable default.",
                        "last_opposing",
                    ),
                    ClarificationOption(
                        "Engulfing candle only", "Stricter but narrower.", "engulfing"
                    ),
                    ClarificationOption(
                        "Highest-volume candle",
                        "Requires volume dependency.",
                        "highest_volume",
                    ),
                ],
                recommended_answer="Last opposing candle before displacement",
                proposed_revision="Define the order block as the last opposing candle before the displacement leg that breaks structure.",
                reason="Order block references are too subjective without selection rules.",
            )
        ]

    def _sweep_timeout_question(self, text: str) -> list[ClarificationQuestion]:
        if "sweep" not in text or any(
            token in text
            for token in (
                "timeout",
                "within 3 candles",
                "within 4 bars",
                "cancel the setup",
            )
        ):
            return []
        return [
            ClarificationQuestion(
                code="sweep_timeout",
                prompt="How many candles after a sweep may the setup remain active?",
                context="Sweep logic exists without an expiry window.",
                options=[
                    ClarificationOption(
                        "3 candles (Recommended)",
                        "Short and replay-friendly.",
                        "3_candles",
                    ),
                    ClarificationOption(
                        "5 candles", "Allows slower confirmation.", "5_candles"
                    ),
                    ClarificationOption(
                        "Until session change",
                        "Expires only at session boundary.",
                        "session_change",
                    ),
                ],
                recommended_answer="3 candles",
                proposed_revision="If confirmation does not occur within 3 candles after the sweep, cancel the setup.",
                reason="Sweep setups need deterministic expiry.",
            )
        ]

    def _cancellation_question(self, text: str) -> list[ClarificationQuestion]:
        if any(
            token in text for token in ("cancel", "invalidation", "invalid", "reject")
        ):
            return []
        return [
            ClarificationQuestion(
                code="cancellation_rules",
                prompt="What exact condition cancels the setup before entry?",
                context="The specification lacks explicit cancellation logic.",
                options=[
                    ClarificationOption(
                        "Cancel on timeout or opposite close (Recommended)",
                        "Most operationally safe default.",
                        "timeout_or_opposite_close",
                    ),
                    ClarificationOption(
                        "Cancel only on session change",
                        "Looser setup persistence.",
                        "session_change",
                    ),
                    ClarificationOption(
                        "Cancel only on opposite structure break",
                        "Structure-only invalidation.",
                        "opposite_break",
                    ),
                ],
                recommended_answer="Cancel on timeout or opposite close",
                proposed_revision="Cancel the setup if confirmation times out or if price closes back through the invalidation level before entry.",
                reason="Without cancellation rules, entry validity remains ambiguous.",
            )
        ]
