from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from core.strategy_registry import get_current_strategy_name
from svos.deployment.service import DeploymentStatusService
from svos.monitoring.service import MonitoringStatusService
from svos.orchestration.service import SVOSPlatform


class SVOSOperationalAPI:
    """Operational API surface for dashboard and service consumers."""

    def __init__(
        self,
        *,
        root: Path | str,
        catalog_path: Path | str | None = None,
        health_snapshot_factory: Callable[[], dict[str, Any]],
        latest_reports_factory: Callable[[], dict[str, Any]],
        control_state_factory: Callable[[], dict[str, Any]],
    ) -> None:
        self.root = Path(root)
        self.catalog_path = (
            Path(catalog_path)
            if catalog_path is not None
            else self.root / "config" / "strategy_catalog.yaml"
        )
        self.platform = SVOSPlatform(root=self.root, catalog_path=self.catalog_path)
        self.deployment = DeploymentStatusService(
            root=self.root, catalog_path=self.catalog_path
        )
        self.monitoring = MonitoringStatusService(
            root=self.root, health_snapshot_factory=health_snapshot_factory
        )
        self.latest_reports_factory = latest_reports_factory
        self.control_state_factory = control_state_factory

    def overview(self) -> dict[str, Any]:
        self.platform.bootstrap()
        registry = self.platform.registry.summary()
        deployment = self.deployment.status()
        monitoring = self.monitoring.snapshot()
        control = self.control_state_factory()
        latest_reports = self.latest_reports_factory()
        return {
            "current_strategy": get_current_strategy_name(self.catalog_path) or "",
            "registry": registry,
            "deployment": deployment,
            "monitoring": monitoring,
            "reports": latest_reports,
            "emergency_stop": control.get("emergency_stop", {}),
            "service_status": {
                "research": "ONLINE",
                "validation": "ONLINE",
                "governance": "ONLINE",
                "deployment": "ONLINE",
                "monitoring": monitoring.get("monitoring_status", "UNKNOWN"),
            },
        }

    def registry_snapshot(self) -> dict[str, Any]:
        self.platform.bootstrap()
        return self.platform.registry.summary()

    def strategy_snapshot(self, strategy: str) -> dict[str, Any]:
        self.platform.bootstrap()
        return self.platform.strategy_summary(strategy)
