from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class CheckResult:
    name: str
    passed: bool
    score: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)
    message: str = ""

