from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Pair(StrEnum):
    EURUSD = "EURUSD"
    GBPUSD = "GBPUSD"
    XAUUSD = "XAUUSD"


class Session(StrEnum):
    LONDON = "London"
    NEW_YORK = "New York"


class StrategySpec(BaseModel):
    """Portable, declarative strategy input. It contains no approval state."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    strategy_id: str = Field(min_length=3, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]+$")
    version: str = Field(default="1.0.0", pattern=r"^\d+\.\d+\.\d+$")
    pair: Pair
    session: Session
    bias: str = Field(min_length=3)
    entry: str = Field(min_length=3)
    risk_pct: float = Field(gt=0, le=2)
    reward_risk: float = Field(gt=0, le=10)
    max_trades_per_day: int = Field(gt=0, le=10)
    stop_loss_required: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("pair", mode="before")
    @classmethod
    def normalize_pair(cls, value: object) -> object:
        return value.upper().replace("/", "") if isinstance(value, str) else value

    @field_validator("session", mode="before")
    @classmethod
    def normalize_session(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        return {"london": "London", "new york": "New York", "new_york": "New York", "ny": "New York"}.get(value.lower(), value)

    @model_validator(mode="after")
    def enforce_execution_safety(self) -> "StrategySpec":
        if not self.stop_loss_required:
            raise ValueError("stop_loss_required must be true")
        return self
