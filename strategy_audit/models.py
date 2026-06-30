from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

AuditStatus = Literal["PASS", "FAIL", "PARTIAL", "NOT_VERIFIED"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class AuditResult:
    name: str
    status: AuditStatus
    score: float
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    recommendation: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_now)

    @property
    def passed(self) -> bool:
        return self.status == "PASS"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AuditContext:
    strategy_name: str
    strategy_text: str = ""
    candles: list[dict[str, Any]] = field(default_factory=list)
    trades: list[dict[str, Any]] = field(default_factory=list)
    execution_report: dict[str, Any] = field(default_factory=dict)
    historical_metrics: dict[str, Any] = field(default_factory=dict)
    live_metrics: dict[str, Any] = field(default_factory=dict)
    data_profile: dict[str, Any] = field(default_factory=dict)
    parameter_grid: dict[str, Any] = field(default_factory=dict)
    regime_breakdown: dict[str, Any] = field(default_factory=dict)
    notes: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AuditReport:
    strategy: str
    created_at: str = field(default_factory=_now)
    module_results: list[AuditResult] = field(default_factory=list)
    overall_status: AuditStatus = "NOT_VERIFIED"
    readiness_score: float = 0.0
    deployment_status: str = "Rejected"
    capital_tier: str = "Research"
    recommended_risk_pct: float = 0.0
    expected_pf: float | None = None
    expected_win_rate: float | None = None
    expected_monthly_dd: float | None = None
    confidence: float = 0.0
    summary: str = ""
    risk_assessment: dict[str, Any] = field(default_factory=dict)
    failure_modes: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    release: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["module_results"] = [item.to_dict() for item in self.module_results]
        return payload
