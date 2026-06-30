"""Historical Replay Integration — Phase 2 of the SVOS qualification pipeline.

Validates that a strategy adapter can step through historical candles without
lookahead, invalid geometry, missing data, or signal-rule disagreement.

Wraps the existing research.validation.engine.ValidationGate and connects its
output to the SVOS evidence repository and governance lifecycle.

Accepts pre-computed replay results (a list of trade dicts produced by any
replay runner) or a minimal ReplayValidationInput dictionary, so the service
remains decoupled from the specific replay executor used.

Lifecycle:
  AUDIT → HISTORICAL_REPLAY  (PASS)
  AUDIT → REFINEMENT         (FAIL)
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from svos.application.run_manifest import RunManifestBuilder
from svos.reports.builders import ReplayReportBuilder

_PASS_STATUSES = {"PASS"}


@dataclass(slots=True)
class ReplayResult:
    strategy: str
    status: str  # PASS | FAIL
    version_id: str
    trade_count: int
    report_artifact: str
    evidence_id: str
    manifest_id: str
    checks: list[dict[str, Any]] = field(default_factory=list)
    replay_summary: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return self.status == "PASS"

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["passed"] = self.passed
        return d


class ReplayIntegrationService:
    """Validates historical replay results and integrates with the SVOS platform."""

    def __init__(self, platform: Any) -> None:
        self._platform = platform
        self._builder = ReplayReportBuilder(platform.root)
        self._manifest_builder = RunManifestBuilder(platform.root)

    def run(
        self,
        strategy: str,
        trades: list[dict[str, Any]],
        *,
        actor: str = "svos-replay",
        dataset_id: str = "",
        replay_summary: dict[str, Any] | None = None,
        available_features: list[str] | None = None,
    ) -> ReplayResult:
        """Validate replay trade results and advance the lifecycle.

        Args:
            strategy: Strategy name registered in the catalog.
            trades: List of trade dicts from any replay runner. Each trade must
                have at minimum: entry_time, exit_time, entry_price, stop_loss,
                take_profit, result_r.
            actor: Identity of the caller.
            dataset_id: Dataset snapshot ID for the run manifest.
            replay_summary: Optional dict with replay run summary metadata.
            available_features: Feature keys confirmed available during replay.

        Returns:
            ReplayResult with PASS/FAIL, full report artifact, and evidence ID.
        """
        manifest_rec = self._manifest_builder.build(
            service="svos.replay",
            strategy=strategy,
            dataset_id=dataset_id,
            parameters={"actor": actor, "trade_count": len(trades)},
        )

        validation_result = self._run_gate(trades, available_features or [])
        status = validation_result.status
        checks = [
            asdict(c) if hasattr(c, "__dataclass_fields__") else dict(c)
            for c in validation_result.checks
        ]
        trade_count = len(trades)

        current = self._platform.registry.ensure_strategy(strategy)

        report_path = self._builder.build_replay_report(
            strategy=strategy,
            version_id=current.current_version_id,
            status=status,
            checks=checks,
            trade_count=trade_count,
            replay_summary=replay_summary or {"trade_count": trade_count},
            manifest=manifest_rec.to_dict(),
        )

        evidence = self._platform.record_report_evidence(
            strategy=strategy,
            stage="HISTORICAL_REPLAY",
            service="svos.replay",
            report_type="replay_report.json",
            artifact_path=report_path,
            status=status,
            metadata={
                "version_id": current.current_version_id,
                "manifest_id": manifest_rec.manifest_id,
                "trade_count": trade_count,
            },
        )

        self._drive_lifecycle(strategy, status, actor, current)

        evidence_id = str(
            evidence.get("evidence", {}).get("evidence_id", "")
            or evidence.get("evidence_id", "")
        )

        return ReplayResult(
            strategy=strategy,
            status=status,
            version_id=current.current_version_id,
            trade_count=trade_count,
            report_artifact=str(report_path),
            evidence_id=evidence_id,
            manifest_id=manifest_rec.manifest_id,
            checks=checks,
            replay_summary=replay_summary or {},
            metadata={"version": current.latest_version},
        )

    def _run_gate(self, trades: list[dict[str, Any]], available_features: list[str]):
        from research.validation.engine import (
            ReplayTrade,
            ReplayValidationInput,
            ValidationGate,
        )

        replay_trades = [
            ReplayTrade(
                trade_id=str(
                    trade.get("trade_id")
                    or trade.get("signal_id")
                    or trade.get("id")
                    or f"trade-{idx}"
                ),
                timestamp=str(
                    trade.get("entry_time")
                    or trade.get("timestamp")
                    or trade.get("opened_at")
                    or ""
                ),
                side=str(
                    trade.get("side")
                    or trade.get("direction")
                    or trade.get("action")
                    or ""
                ),
                entry_price=float(
                    trade.get("entry_price") or trade.get("entry") or 0.0
                ),
                stop_loss=float(trade.get("stop_loss") or trade.get("sl") or 0.0),
                take_profit=float(trade.get("take_profit") or trade.get("tp") or 0.0),
                position_size=float(
                    trade.get("position_size") or trade.get("lots") or 0.0
                ),
                required_features=list(trade.get("required_features") or []),
            )
            for idx, trade in enumerate(trades, start=1)
        ]

        payload = ReplayValidationInput(
            completed_successfully=len(trades) > 0,
            trades=replay_trades,
            exceptions=[],
            state_transitions=[],
            required_features=[],
            available_features=available_features,
            missing_timestamps=[],
            has_uncaught_exceptions=False,
        )
        gate = ValidationGate()
        return gate.validate_replay(payload)

    def _drive_lifecycle(
        self, strategy: str, status: str, actor: str, current: Any
    ) -> None:
        current_stage = str(current.current_stage)
        if status == "PASS" and current_stage == "AUDIT":
            target, reason = "HISTORICAL_REPLAY", "Replay validation passed"
        elif status == "FAIL" and current_stage in ("AUDIT", "HISTORICAL_REPLAY"):
            target, reason = (
                "REFINEMENT",
                "Replay validation failed — requires spec revision",
            )
        else:
            return
        try:
            self._platform.audited_transition(
                strategy, to_stage=target, actor=actor, reason=reason
            )
        except Exception as exc:
            if "No PASS evidence" not in str(exc) and "Illegal lifecycle" not in str(
                exc
            ):
                raise
