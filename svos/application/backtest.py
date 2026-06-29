"""Backtest Integration — Phase 3 of the SVOS qualification pipeline.

Validates that a strategy has a statistically meaningful edge net of fees.

The canonical Phase-0 gate (per CLAUDE.md §7):
  n >= 50  AND  net PF > 1.0  at BOTH standard AND 2× spread stress.

Wraps research.validation.engine.ValidationGate.validate_backtest() and
connects the result to SVOS evidence + governance lifecycle.

Accepts a BacktestMetrics dict so the service is decoupled from the
specific backtest executor (TradeSimulator, vectorbt, etc.).

Lifecycle:
  HISTORICAL_REPLAY → STATISTICAL_VALIDATION  (PASS)
  HISTORICAL_REPLAY → REFINEMENT              (FAIL)
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from svos.application.run_manifest import RunManifestBuilder
from svos.reports.builders import BacktestReportBuilder


_MIN_TRADE_COUNT = 50
_MIN_PROFIT_FACTOR = 1.0


@dataclass(slots=True)
class BacktestResult:
    strategy: str
    status: str
    version_id: str
    report_artifact: str
    evidence_id: str
    manifest_id: str
    metrics: dict[str, Any] = field(default_factory=dict)
    checks: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return self.status == "PASS"

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["passed"] = self.passed
        return d


class BacktestIntegrationService:
    """Validates backtest metrics against the Phase-0 gate and advances the lifecycle."""

    def __init__(self, platform: Any) -> None:
        self._platform = platform
        self._builder = BacktestReportBuilder(platform.root)
        self._manifest_builder = RunManifestBuilder(platform.root)

    def run(
        self,
        strategy: str,
        metrics: dict[str, Any],
        *,
        actor: str = "svos-backtest",
        dataset_id: str = "",
        cost_model: dict[str, Any] | None = None,
    ) -> BacktestResult:
        """Validate backtest metrics against the Phase-0 gate.

        Args:
            strategy: Strategy name registered in the catalog.
            metrics: Dict with keys: trade_count, profit_factor, profit_factor_2x,
                expectancy, max_drawdown, win_rate, spread_included,
                commission_included. Additional keys are preserved.
            actor: Identity of the caller.
            dataset_id: Dataset snapshot ID for the run manifest.
            cost_model: Cost model description (spread, commission, slippage).

        Returns:
            BacktestResult with PASS/FAIL, full report artifact, and evidence ID.
        """
        manifest_rec = self._manifest_builder.build(
            service="svos.backtest",
            strategy=strategy,
            dataset_id=dataset_id,
            parameters={"actor": actor, "trade_count": int(metrics.get("trade_count", 0))},
        )

        checks = self._evaluate_gate(metrics)
        status = "PASS" if all(c["passed"] for c in checks if c.get("severity") == "ERROR") else "FAIL"

        current = self._platform.registry.ensure_strategy(strategy)

        report_path = self._builder.build_backtest_report(
            strategy=strategy,
            version_id=current.current_version_id,
            status=status,
            checks=checks,
            metrics=metrics,
            cost_model=cost_model or self._default_cost_model(),
            manifest=manifest_rec.to_dict(),
        )

        evidence = self._platform.record_report_evidence(
            strategy=strategy,
            stage="STATISTICAL_VALIDATION",
            service="svos.backtest",
            report_type="backtest_report.json",
            artifact_path=report_path,
            status=status,
            metadata={
                "version_id": current.current_version_id,
                "manifest_id": manifest_rec.manifest_id,
                "profit_factor": float(metrics.get("profit_factor", 0.0)),
                "profit_factor_2x": float(metrics.get("profit_factor_2x", 0.0)),
                "trade_count": int(metrics.get("trade_count", 0)),
            },
        )

        self._drive_lifecycle(strategy, status, actor, current, metrics)

        evidence_id = str(
            evidence.get("evidence", {}).get("evidence_id", "")
            or evidence.get("evidence_id", "")
        )

        return BacktestResult(
            strategy=strategy,
            status=status,
            version_id=current.current_version_id,
            report_artifact=str(report_path),
            evidence_id=evidence_id,
            manifest_id=manifest_rec.manifest_id,
            metrics=metrics,
            checks=checks,
            metadata={"version": current.latest_version},
        )

    # ── gate evaluation ────────────────────────────────────────────────────

    def _evaluate_gate(self, metrics: dict[str, Any]) -> list[dict[str, Any]]:
        checks: list[dict[str, Any]] = []
        n = int(metrics.get("trade_count", 0))
        pf = float(metrics.get("profit_factor", 0.0))
        pf_2x = float(metrics.get("profit_factor_2x", 0.0))
        expectancy = float(metrics.get("expectancy", 0.0))
        max_dd = float(metrics.get("max_drawdown", 0.0))
        spread_ok = metrics.get("spread_included", None)
        commission_ok = metrics.get("commission_included", None)

        checks.append({
            "name": "minimum_trade_count",
            "passed": n >= _MIN_TRADE_COUNT,
            "severity": "ERROR",
            "message": f"n={n} (required ≥ {_MIN_TRADE_COUNT})",
        })
        checks.append({
            "name": "profit_factor_standard",
            "passed": pf > _MIN_PROFIT_FACTOR,
            "severity": "ERROR",
            "message": f"PF={pf:.3f} (required > {_MIN_PROFIT_FACTOR})",
        })
        checks.append({
            "name": "profit_factor_2x_stress",
            "passed": pf_2x > _MIN_PROFIT_FACTOR,
            "severity": "ERROR",
            "message": f"PF_2x={pf_2x:.3f} (required > {_MIN_PROFIT_FACTOR})",
        })
        checks.append({
            "name": "positive_expectancy",
            "passed": expectancy > 0.0,
            "severity": "ERROR",
            "message": f"expectancy={expectancy:.4f}R (required > 0)",
        })
        checks.append({
            "name": "spread_cost_included",
            "passed": spread_ok is not False,
            "severity": "ERROR",
            "message": "Spread cost must be applied — a result without spread is not a result.",
        })
        checks.append({
            "name": "commission_cost_included",
            "passed": commission_ok is not False,
            "severity": "WARN",
            "message": "Commission cost should be applied for institutional-grade results.",
        })
        if max_dd > 0:
            checks.append({
                "name": "drawdown_below_policy",
                "passed": max_dd <= 20.0,
                "severity": "WARN",
                "message": f"max_drawdown={max_dd:.2f}% (warn threshold 20%)",
            })
        return checks

    @staticmethod
    def _default_cost_model() -> dict[str, Any]:
        return {
            "source": "vantage_standard",
            "EURUSD_spread_pips": 0.8,
            "GBPUSD_spread_pips": 1.2,
            "commission_pips": 0.0,
            "stress_multiplier": 2.0,
        }

    def _drive_lifecycle(
        self,
        strategy: str,
        status: str,
        actor: str,
        current: Any,
        metrics: dict[str, Any],
    ) -> None:
        current_stage = str(current.current_stage)
        pf = float(metrics.get("profit_factor", 0.0))
        pf_2x = float(metrics.get("profit_factor_2x", 0.0))
        n = int(metrics.get("trade_count", 0))

        if status == "PASS" and current_stage == "HISTORICAL_REPLAY":
            target = "STATISTICAL_VALIDATION"
            reason = f"Phase-0 gate passed (n={n}, PF={pf:.3f}, PF_2x={pf_2x:.3f})"
        elif status == "FAIL" and current_stage in ("HISTORICAL_REPLAY", "STATISTICAL_VALIDATION"):
            target = "REFINEMENT"
            reason = f"Phase-0 gate failed (n={n}, PF={pf:.3f}, PF_2x={pf_2x:.3f})"
        else:
            return
        try:
            self._platform.audited_transition(strategy, to_stage=target, actor=actor, reason=reason)
        except Exception as exc:
            if "No PASS evidence" not in str(exc) and "Illegal lifecycle" not in str(exc):
                raise
