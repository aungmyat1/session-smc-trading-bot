"""Consolidated production deployment status summary."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from shared.serialization import read_json


@dataclass(frozen=True, slots=True)
class ProductionDeploymentSummary:
    deployment_id: str
    strategy: str
    version: str
    overall_status: str
    next_action: str
    deployment: dict[str, Any]
    imported: dict[str, Any]
    preflight: dict[str, Any]
    activation: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ProductionSummaryService:
    """Aggregate deployment state into one operator-facing snapshot."""

    def __init__(self, *, root: Path | str) -> None:
        self.root = Path(root)
        self.deployment_root = self.root / "data" / "svos" / "deployment"
        self.import_root = self.root / "data" / "production" / "imports"
        self.activation_root = self.root / "data" / "production" / "activations"

    def summarize(self, deployment_id: str) -> ProductionDeploymentSummary:
        deployment = self._read_required(
            self.deployment_root / "deployments" / deployment_id / "state.json",
            f"deployment not found: {deployment_id}",
        )
        imported = self._read_optional(self.import_root / deployment_id / "import_state.json")
        preflight = self._read_optional(self.import_root / deployment_id / "preflight_verification.json")
        activation = self._read_optional(self.activation_root / deployment_id / "activation_state.json")

        overall_status, next_action = self._derive_overall_status(imported, preflight, activation)
        return ProductionDeploymentSummary(
            deployment_id=deployment_id,
            strategy=str(deployment.get("strategy", "")),
            version=str(deployment.get("version", "")),
            overall_status=overall_status,
            next_action=next_action,
            deployment=deployment,
            imported=imported,
            preflight=preflight,
            activation=activation,
        )

    @staticmethod
    def _read_required(path: Path, error: str) -> dict[str, Any]:
        payload = read_json(path, {})
        if not payload:
            raise KeyError(error)
        return payload

    @staticmethod
    def _read_optional(path: Path) -> dict[str, Any]:
        payload = read_json(path, {})
        return payload if isinstance(payload, dict) else {}

    @staticmethod
    def _derive_overall_status(
        imported: dict[str, Any],
        preflight: dict[str, Any],
        activation: dict[str, Any],
    ) -> tuple[str, str]:
        if not imported:
            return "DEPLOYMENT_CREATED", "Run production import."
        if not bool(imported.get("verified", False)):
            return "IMPORT_FAILED", "Re-import deployment package and verify checksum."
        if not preflight:
            return "IMPORTED", "Run production preflight verification."
        if not bool(preflight.get("verified", False)):
            return "PREFLIGHT_BLOCKED", "Inspect preflight report and fix package issues."
        if not activation:
            return "READY_DISABLED", "Stage disabled runtime attachment."
        status = str(activation.get("activation_status", ""))
        if status == "BLOCKED":
            return "ACTIVATION_BLOCKED", str(activation.get("reason", "Activation blocked."))
        if status == "STAGED_DISABLED":
            return "STAGED_DISABLED", "Deployment is fully staged and remains disabled."
        return "READY_DISABLED", "Review activation state."
