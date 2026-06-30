from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from core.strategy_registry import get_current_strategy_manifest, get_current_strategy_name


class DeploymentStatusService:
    """Read-only deployment status view over existing runtime configuration."""

    def __init__(self, *, root: Path | str, catalog_path: Path | str | None = None) -> None:
        self.root = Path(root)
        self.catalog_path = Path(catalog_path) if catalog_path is not None else self.root / "config" / "strategy_catalog.yaml"

    def status(self) -> dict[str, Any]:
        current = get_current_strategy_name(self.catalog_path) or ""
        manifest = get_current_strategy_manifest(self.catalog_path) or {}
        live_trading = os.getenv("LIVE_TRADING", "false").lower() == "true"
        demo_only = os.getenv("DEMO_ONLY", "true").lower() == "true"
        return {
            "current_strategy": current,
            "deployment_target": manifest.get("deployment_target", "unknown"),
            "legacy_status": manifest.get("status", "draft"),
            "svos_stage": manifest.get("svos_stage", ""),
            "approved": bool(manifest.get("approved", False)),
            "live_trading": live_trading,
            "demo_only": demo_only,
            "deployment_readiness": "BLOCKED" if live_trading or not demo_only else "SAFE_CONSTRUCTION",
        }
