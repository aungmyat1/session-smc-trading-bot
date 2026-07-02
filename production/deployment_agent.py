"""Idempotent production deployment agent for disabled strategy staging."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from production.activation import ProductionActivationService
from production.importer import DeploymentImportService
from production.summary import ProductionSummaryService
from production.verifier import ProductionPreflightVerifier
from shared.serialization import now_iso, read_json, write_json


class ProductionDeploymentAgent:
    def __init__(self, *, root: Path | str) -> None:
        self.root = Path(root)
        self.deployments_root = self.root / "data" / "svos" / "deployment" / "deployments"
        self.agent_state = self.root / "data" / "production" / "deployment_agent.json"

    def deploy_disabled(self, deployment_id: str, *, actor: str = "deployment-agent") -> dict[str, Any]:
        imported = DeploymentImportService(root=self.root).import_deployment(deployment_id)
        preflight = ProductionPreflightVerifier(root=self.root).verify_import(deployment_id)
        if not preflight.verified:
            return ProductionSummaryService(root=self.root).summarize(deployment_id).to_dict()
        ProductionActivationService(root=self.root).stage_runtime(deployment_id, actor=actor)
        summary = ProductionSummaryService(root=self.root).summarize(deployment_id).to_dict()
        write_json(
            self.agent_state,
            {"last_poll_at": now_iso(), "last_deployment_id": deployment_id, "last_status": summary["overall_status"], "import_verified": imported.verified},
        )
        return summary

    def poll_once(self, *, actor: str = "deployment-agent") -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        if not self.deployments_root.exists():
            return results
        for state_path in sorted(self.deployments_root.glob("*/state.json")):
            deployment = read_json(state_path, {})
            deployment_id = str(deployment.get("deployment_id", ""))
            if not deployment_id or str(deployment.get("status", "")) not in {"READY_DISABLED", "CREATED"}:
                continue
            activation = read_json(
                self.root / "data" / "production" / "activations" / deployment_id / "activation_state.json",
                {},
            )
            if activation.get("activation_status") == "STAGED_DISABLED":
                continue
            results.append(self.deploy_disabled(deployment_id, actor=actor))
        write_json(self.agent_state, {"last_poll_at": now_iso(), "processed": len(results)})
        return results

    def status(self) -> dict[str, Any]:
        return read_json(self.agent_state, {"last_poll_at": "", "processed": 0})
