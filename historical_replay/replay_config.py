from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


class ReplayConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pair: str
    start: datetime
    end: datetime
    data_path: Path
    output_dir: Path = Path("reports/replay")

    @field_validator("pair")
    @classmethod
    def supported_pair(cls, value: str) -> str:
        pair = value.upper().replace("/", "")
        if pair not in {"EURUSD", "GBPUSD", "XAUUSD"}:
            raise ValueError("pair must be EURUSD, GBPUSD, or XAUUSD")
        return pair

    @model_validator(mode="after")
    def chronological_window(self) -> "ReplayConfig":
        if self.end < self.start:
            raise ValueError("end must not precede start")
        return self
