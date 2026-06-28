"""Regression comparison engine for latest vs previous successful runs."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

import math
import json


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("nan")


def _is_nan(value: Any) -> bool:
    return isinstance(value, float) and math.isnan(value)


@dataclass
class RegressionThresholds:
    warning_drop_pct: float = 0.05
    fail_drop_pct: float = 0.10
    warning_increase_pct: float = 0.10
    fail_increase_pct: float = 0.20


@dataclass
class RegressionComparison:
    metric: str
    latest: float
    previous: float
    delta: float
    delta_pct: float
    status: str
    message: str


@dataclass
class RegressionResult:
    status: str
    comparisons: list[RegressionComparison] = field(default_factory=list)
    created_at: str = field(default_factory=_now)
    summary: str = ""
    baseline_available: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "comparisons": [asdict(c) for c in self.comparisons],
            "created_at": self.created_at,
            "summary": self.summary,
            "baseline_available": self.baseline_available,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True, default=str)

    def to_markdown(self) -> str:
        lines = [
            "## Regression Analysis",
            "",
            f"- Status: **{self.status}**",
            f"- Timestamp: `{self.created_at}`",
        ]
        if self.summary:
            lines.extend(["", self.summary])
        lines.extend(["", "| Metric | Latest | Previous | Delta | Delta % | Status |", "|---|---:|---:|---:|---:|---|"])
        for comp in self.comparisons:
            lines.append(
                f"| {comp.metric} | {comp.latest:.4f} | {comp.previous:.4f} | {comp.delta:.4f} | {comp.delta_pct:.2%} | {comp.status} |"
            )
        return "\n".join(lines) + "\n"

    def to_html(self) -> str:
        rows = []
        for comp in self.comparisons:
            rows.append(
                "<tr>"
                f"<td>{comp.metric}</td>"
                f"<td>{comp.latest:.4f}</td>"
                f"<td>{comp.previous:.4f}</td>"
                f"<td>{comp.delta:.4f}</td>"
                f"<td>{comp.delta_pct:.2%}</td>"
                f"<td>{comp.status}</td>"
                "</tr>"
            )
        return (
            "<section>"
            "<h2>Regression Analysis</h2>"
            f"<p><strong>Status:</strong> {self.status}</p>"
            + (f"<p>{self.summary}</p>" if self.summary else "")
            + "<table><thead><tr><th>Metric</th><th>Latest</th><th>Previous</th><th>Delta</th><th>Delta %</th><th>Status</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table>"
            "</section>"
        )


class RegressionEngine:
    """Compare latest metrics against a previous successful baseline."""

    def __init__(self, thresholds: dict[str, dict[str, float]] | None = None) -> None:
        self.thresholds = thresholds or {}

    def compare(
        self,
        latest: dict[str, Any],
        previous: dict[str, Any] | None = None,
    ) -> RegressionResult:
        if not previous:
            return RegressionResult(
                status="PASS",
                comparisons=[],
                summary="No previous successful run available; regression baseline skipped.",
                baseline_available=False,
            )

        comparisons: list[RegressionComparison] = []
        overall = "PASS"
        for metric in ("profit_factor", "win_rate", "expectancy", "max_drawdown", "trade_count", "net_return"):
            latest_v = _safe_float(latest.get(metric))
            previous_v = _safe_float(previous.get(metric))
            if _is_nan(latest_v) and _is_nan(previous_v):
                continue
            if _is_nan(latest_v) or _is_nan(previous_v):
                comparisons.append(
                    RegressionComparison(
                        metric=metric,
                        latest=latest_v,
                        previous=previous_v,
                        delta=float("nan"),
                        delta_pct=float("nan"),
                        status="FAIL",
                        message="NaN metric encountered",
                    )
                )
                overall = "FAIL"
                continue

            delta = latest_v - previous_v
            delta_pct = 0.0 if previous_v == 0 else delta / abs(previous_v)
            metric_thresholds = self.thresholds.get(metric, {})

            if metric == "max_drawdown":
                warn_pct = float(metric_thresholds.get("warning_increase_pct", 0.10))
                fail_pct = float(metric_thresholds.get("fail_increase_pct", 0.20))
                if delta_pct > fail_pct:
                    status = "FAIL"
                elif delta_pct > warn_pct:
                    status = "WARNING"
                else:
                    status = "PASS"
            else:
                warn_pct = float(metric_thresholds.get("warning_drop_pct", 0.05))
                fail_pct = float(metric_thresholds.get("fail_drop_pct", 0.10))
                if previous_v > 0 and delta_pct < -fail_pct:
                    status = "FAIL"
                elif previous_v > 0 and delta_pct < -warn_pct:
                    status = "WARNING"
                elif previous_v <= 0 and latest_v < previous_v:
                    status = "FAIL"
                elif previous_v <= 0 and latest_v == previous_v:
                    status = "WARNING"
                else:
                    status = "PASS"

            message = f"{metric} latest={latest_v:.4f} previous={previous_v:.4f}"
            comparisons.append(
                RegressionComparison(
                    metric=metric,
                    latest=latest_v,
                    previous=previous_v,
                    delta=delta,
                    delta_pct=delta_pct,
                    status=status,
                    message=message,
                )
            )
            if status == "FAIL":
                overall = "FAIL"
            elif status == "WARNING" and overall != "FAIL":
                overall = "WARNING"

        if not comparisons:
            summary = "No comparable regression metrics provided; regression comparison skipped."
        else:
            summary = {
                "PASS": "Latest run remains within regression thresholds.",
                "WARNING": "Latest run shows manageable regression drift.",
                "FAIL": "Latest run regressed beyond configured thresholds.",
            }[overall]
        return RegressionResult(status=overall, comparisons=comparisons, summary=summary)
