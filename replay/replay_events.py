from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any


class ReplayEventType(StrEnum):
    REPLAY_STARTED = "replay_started"
    MARKET_BAR_EMITTED = "market_bar_emitted"
    STRATEGY_SIGNAL_GENERATED = "strategy_signal_generated"
    RISK_DECISION_RECORDED = "risk_decision_recorded"
    ORDER_INTENT_CREATED = "order_intent_created"
    ORDER_INTENT_REJECTED = "order_intent_rejected"
    REPLAY_FINISHED = "replay_finished"
    REPLAY_FAILED = "replay_failed"


@dataclass(frozen=True, slots=True)
class ReplayEvent:
    run_id: str
    event_type: ReplayEventType
    timestamp: datetime
    payload: dict[str, Any]
    sequence_number: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "payload": self.payload,
            "sequence_number": self.sequence_number,
        }
