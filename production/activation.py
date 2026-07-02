"""Guarded production activation state machine.

This module does not enable live trading. It records whether a deployment has
been staged for runtime attachment while enforcing the construction-time
invariants that keep LIVE_TRADING disabled.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from shared.serialization import now_iso, read_json, write_json


@dataclass(frozen=True, slots=True)
class ActivationRecord:
    deployment_id: str
    strategy: str
    version: str
    requested_by: str
    requested_at: str
    activation_status: str
    runtime_ready: bool
    activated: bool
    live_trading_enabled: bool
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ProductionActivationService:
    """Record disabled runtime staging while blocking any live activation path."""

    def __init__(self, *, root: Path | str) -> None:
        self.root = Path(root)
        self.deployment_root = self.root / "data" / "svos" / "deployment"
        self.import_root = self.root / "data" / "production" / "imports"
        self.activation_root = self.root / "data" / "production" / "activations"

    def stage_runtime(self, deployment_id: str, *, actor: str = "system", request_live: bool = False) -> ActivationRecord:
        deployment = self._load_deployment(deployment_id)
        imported = self._load_import(deployment_id)
        preflight = self._load_preflight(deployment_id)
        requested_at = now_iso()

        live_trading = os.getenv("LIVE_TRADING", "false").lower() == "true"
        demo_only = os.getenv("DEMO_ONLY", "true").lower() == "true"
        preflight_verified = bool(preflight.get("verified", False))
        preflight_verdict = str(preflight.get("verdict", ""))
        import_verified = bool(imported.get("verified", False))

        blocked_reason = ""
        if request_live:
            blocked_reason = "Live activation requests are blocked by construction policy."
        elif live_trading or not demo_only:
            blocked_reason = "Environment policy requires LIVE_TRADING=false and DEMO_ONLY=true."
        elif not import_verified:
            blocked_reason = "Deployment package import is not verified."
        elif not preflight_verified or preflight_verdict != "READY_DISABLED":
            blocked_reason = "Preflight verification did not produce READY_DISABLED."

        if blocked_reason:
            record = ActivationRecord(
                deployment_id=deployment_id,
                strategy=str(deployment.get("strategy", "")),
                version=str(deployment.get("version", "")),
                requested_by=actor,
                requested_at=requested_at,
                activation_status="BLOCKED",
                runtime_ready=False,
                activated=False,
                live_trading_enabled=False,
                reason=blocked_reason,
            )
        else:
            record = ActivationRecord(
                deployment_id=deployment_id,
                strategy=str(deployment.get("strategy", "")),
                version=str(deployment.get("version", "")),
                requested_by=actor,
                requested_at=requested_at,
                activation_status="STAGED_DISABLED",
                runtime_ready=True,
                activated=False,
                live_trading_enabled=False,
                reason="Deployment imported and preflighted; runtime remains staged but disabled.",
            )

        path = self.activation_root / deployment_id / "activation_state.json"
        write_json(path, record.to_dict())
        return record

    def activation_status(self, deployment_id: str) -> dict[str, Any]:
        path = self.activation_root / deployment_id / "activation_state.json"
        payload = read_json(path, {})
        if not payload:
            raise KeyError(f"activation state not found for deployment: {deployment_id}")
        return payload

    def _load_deployment(self, deployment_id: str) -> dict[str, Any]:
        path = self.deployment_root / "deployments" / deployment_id / "state.json"
        payload = read_json(path, {})
        if not payload:
            raise KeyError(f"deployment not found: {deployment_id}")
        return payload

    def _load_import(self, deployment_id: str) -> dict[str, Any]:
        path = self.import_root / deployment_id / "import_state.json"
        payload = read_json(path, {})
        if not payload:
            raise KeyError(f"import not found for deployment: {deployment_id}")
        return payload

    def _load_preflight(self, deployment_id: str) -> dict[str, Any]:
        path = self.import_root / deployment_id / "preflight_verification.json"
        payload = read_json(path, {})
        if not payload:
            raise KeyError(f"preflight verification not found: {deployment_id}")
        return payload
