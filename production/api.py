"""Read-only facade for production operational state."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from production.observability import ProductionObservabilityService
from production.operations import OperationsRepository
from shared.serialization import read_json


class ProductionReadAPI:
    def __init__(self, repository: OperationsRepository, observability: ProductionObservabilityService, *, root: Path | str = ".") -> None:
        self.repository = repository
        self.observability = observability
        self.root = Path(root)

    def status(self) -> dict[str, Any]:
        return {"health": self.health(), "runtime": read_json(self.root / "data/production/runtime/runtime-state.json", {})}

    def package(self) -> dict[str, Any]:
        runtime = read_json(self.root / "data/production/runtime/runtime-state.json", {})
        return {key: runtime.get(key) for key in ("package_id", "package_sha256", "strategy_id", "strategy_version")}

    def reports(self) -> list[dict[str, Any]]:
        base = self.root / "reports" / "production"
        result = []
        for path in sorted(base.glob("*/*.json")) if base.exists() else []:
            payload = read_json(path, {})
            result.append({"path": str(path), "report_id": payload.get("report_id"), "report_type": payload.get("report_type")})
        return result

    def health(self) -> dict[str, Any]:
        return self.observability.health()

    def metrics(self) -> str:
        return self.observability.metrics()

    def records(self, resource: str, *, limit: int = 100) -> list[dict[str, Any]]:
        mapping = {"runtime": "runtime", "market-data": "market_data_health", "risk": "risk_decision", "orders": "order_record", "positions": "position_record", "incidents": "incident", "recovery": "recovery_checkpoint", "events": "execution_event"}
        if resource not in mapping:
            raise KeyError(resource)
        return [dict(value) for value in self.repository.list_records(mapping[resource], limit=limit)]
