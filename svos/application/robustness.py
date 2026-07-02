"""Robustness Validation Integration — Phase 4 of the SVOS qualification pipeline.

Runs walk-forward analysis, Monte Carlo resampling, parameter sensitivity, and
regime analysis to verify the strategy edge is stable across time, parameters,
and market conditions.

Wraps research.robustness (walk_forward_analysis, monte_carlo_resampling,
parameter_sensitivity, regime_analysis) and connects results to SVOS evidence
+ governance lifecycle.

A PASS requires walk-forward, Monte Carlo, parameter sensitivity, and regime
analysis to all pass. Missing or malformed supplemental robustness inputs fail
closed rather than being silently downgraded.

Lifecycle:
  STATISTICAL_VALIDATION → ROBUSTNESS_VALIDATION  (PASS)
  STATISTICAL_VALIDATION → REFINEMENT             (FAIL)
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from svos.application.run_manifest import RunManifestBuilder
from svos.reports.builders import RobustnessReportBuilder


@dataclass(slots=True)
class RobustnessResult:
    strategy: str
    status: str
    version_id: str
    report_artifact: str
    evidence_id: str
    manifest_id: str
    walk_forward: dict[str, Any] = field(default_factory=dict)
    monte_carlo: dict[str, Any] = field(default_factory=dict)
    sensitivity: dict[str, Any] = field(default_factory=dict)
    regime: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return self.status == "PASS"

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["passed"] = self.passed
        return d


class RobustnessIntegrationService:
    """Runs robustness tests and integrates with the SVOS platform."""

    def __init__(self, platform: Any) -> None:
        self._platform = platform
        self._builder = RobustnessReportBuilder(platform.root)
        self._manifest_builder = RunManifestBuilder(platform.root)

    def run(
        self,
        strategy: str,
        trades: list[dict[str, Any]],
        *,
        actor: str = "svos-robustness",
        dataset_id: str = "",
        parameter_grid: list[dict[str, Any]] | dict[str, Any] | None = None,
        regime_labels: list[str] | None = None,
        r_key: str = "result_r",
    ) -> RobustnessResult:
        """Run all robustness tests and register evidence.

        Args:
            strategy: Strategy name in the catalog.
            trades: List of completed trade dicts. Each must have the field
                specified by r_key (default "result_r") plus entry_time.
            actor: Caller identity.
            dataset_id: Dataset snapshot ID.
            parameter_grid: Optional parameter-sweep payload for sensitivity
                analysis. Accepts either the native rr-results mapping expected
                by ``research.robustness.parameter_sensitivity`` or a list of
                sweep points that include an RR key plus a profit-factor metric.
            regime_labels: Optional list of regime label strings (one per trade)
                for regime-slice analysis.
            r_key: Key used to read the net R value from each trade dict.

        Returns:
            RobustnessResult with PASS/FAIL and all component results.
        """
        manifest_rec = self._manifest_builder.build(
            service="svos.robustness",
            strategy=strategy,
            dataset_id=dataset_id,
            parameters={"actor": actor, "trade_count": len(trades)},
        )

        # Normalise the r_key so all engines read the same field
        normalized = self._normalize_trades(trades, r_key)

        wf = self._run_walk_forward(normalized)
        mc = self._run_monte_carlo(normalized)
        sens = self._run_sensitivity(parameter_grid)
        reg = self._run_regime(normalized, regime_labels)

        # PASS = all four robustness gates passing.
        hard_pass = all(
            component.get("passed", False)
            for component in (wf, mc, sens, reg)
        )
        status = "PASS" if hard_pass else "FAIL"

        current = self._platform.registry.ensure_strategy(strategy)

        report_path = self._builder.build_robustness_report(
            strategy=strategy,
            version_id=current.current_version_id,
            status=status,
            walk_forward=wf,
            monte_carlo=mc,
            sensitivity=sens,
            regime=reg,
            manifest=manifest_rec.to_dict(),
        )

        evidence = self._platform.record_report_evidence(
            strategy=strategy,
            stage="ROBUSTNESS_VALIDATION",
            service="svos.robustness",
            report_type="robustness_report.json",
            artifact_path=report_path,
            status=status,
            metadata={
                "version_id": current.current_version_id,
                "manifest_id": manifest_rec.manifest_id,
                "walk_forward_passed": wf.get("passed", False),
                "monte_carlo_passed": mc.get("passed", False),
            },
        )

        self._drive_lifecycle(strategy, status, actor, current)

        evidence_id = str(
            evidence.get("evidence", {}).get("evidence_id", "")
            or evidence.get("evidence_id", "")
        )

        return RobustnessResult(
            strategy=strategy,
            status=status,
            version_id=current.current_version_id,
            report_artifact=str(report_path),
            evidence_id=evidence_id,
            manifest_id=manifest_rec.manifest_id,
            walk_forward=wf,
            monte_carlo=mc,
            sensitivity=sens,
            regime=reg,
            metadata={"version": current.latest_version, "trade_count": len(trades)},
        )

    # ── engine wrappers ────────────────────────────────────────────────────

    @staticmethod
    def _normalize_trades(trades: list[dict[str, Any]], r_key: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for t in trades:
            if not isinstance(t, dict):
                continue
            r_val = t.get(r_key) or t.get("result_r") or t.get("std_net_r")
            if r_val is None:
                continue
            rows.append({**t, "std_net_r": float(r_val)})
        return rows

    @staticmethod
    def _run_walk_forward(trades: list[dict[str, Any]]) -> dict[str, Any]:
        try:
            from research.robustness import walk_forward_analysis
            return walk_forward_analysis(trades, r_key="std_net_r")
        except Exception as exc:
            return {"passed": False, "reason": str(exc), "folds": []}

    @staticmethod
    def _run_monte_carlo(trades: list[dict[str, Any]]) -> dict[str, Any]:
        try:
            from research.robustness import monte_carlo_resampling
            return monte_carlo_resampling(trades, r_key="std_net_r")
        except Exception as exc:
            return {"passed": False, "reason": str(exc), "iterations": 0}

    @staticmethod
    def _run_sensitivity(parameter_grid: list[dict[str, Any]] | dict[str, Any] | None) -> dict[str, Any]:
        rr_results = RobustnessIntegrationService._normalize_parameter_grid(parameter_grid)
        if not rr_results:
            return {"passed": False, "reason": "no_parameter_grid"}
        try:
            from research.robustness import parameter_sensitivity
            return parameter_sensitivity(rr_results)
        except Exception as exc:
            return {"passed": False, "reason": str(exc), "rr_results": rr_results}

    @staticmethod
    def _run_regime(trades: list[dict[str, Any]], regime_labels: list[str] | None) -> dict[str, Any]:
        try:
            from research.robustness import regime_analysis
            return regime_analysis(
                RobustnessIntegrationService._merge_regime_labels(trades, regime_labels),
                r_key="std_net_r",
            )
        except Exception as exc:
            return {"passed": False, "reason": str(exc), "regimes": []}

    @staticmethod
    def _normalize_parameter_grid(parameter_grid: list[dict[str, Any]] | dict[str, Any] | None) -> dict[str, Any]:
        if isinstance(parameter_grid, dict):
            return parameter_grid
        if not isinstance(parameter_grid, list):
            return {}

        rr_results: dict[str, Any] = {}
        for row in parameter_grid:
            if not isinstance(row, dict):
                continue
            rr_value = (
                row.get("rr")
                or row.get("reward_risk")
                or row.get("reward_risk_ratio")
                or row.get("rr_ratio")
                or row.get("take_profit_r")
            )
            if rr_value is None:
                continue

            metrics = row.get("std_metrics") if isinstance(row.get("std_metrics"), dict) else None
            if metrics is None:
                net_pf = row.get("net_pf") or row.get("profit_factor")
                if net_pf is None:
                    continue
                metrics = {"net_pf": float(net_pf)}
            rr_results[str(rr_value)] = {"std_metrics": metrics}
        return rr_results

    @staticmethod
    def _merge_regime_labels(trades: list[dict[str, Any]], regime_labels: list[str] | None) -> list[dict[str, Any]]:
        if regime_labels is None:
            return trades
        if len(regime_labels) != len(trades):
            raise ValueError("regime label count must match trade count")
        merged: list[dict[str, Any]] = []
        for trade, regime in zip(trades, regime_labels, strict=True):
            merged.append({**trade, "regime": regime})
        return merged

    def _drive_lifecycle(self, strategy: str, status: str, actor: str, current: Any) -> None:
        current_stage = str(current.current_stage)
        if status == "PASS" and current_stage == "STATISTICAL_VALIDATION":
            target, reason = "ROBUSTNESS_VALIDATION", "Robustness validation passed"
        elif status == "FAIL" and current_stage in ("STATISTICAL_VALIDATION", "ROBUSTNESS_VALIDATION"):
            target, reason = "REFINEMENT", "Robustness validation failed — walk-forward or Monte Carlo did not pass"
        else:
            return
        try:
            self._platform.audited_transition(strategy, to_stage=target, actor=actor, reason=reason)
        except Exception as exc:
            if "No PASS evidence" not in str(exc) and "Illegal lifecycle" not in str(exc):
                raise
