from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from approval_package.package_validator import validate_package


class PackageRegistry:
    def __init__(self, path: Path | str = "reports/approved_packages/registry.json") -> None:
        self.path = Path(path)

    def register(self, package: Path | str, *, signing_key: str | None = None) -> dict[str, Any]:
        result = validate_package(package, signing_key=signing_key)
        result.require_valid()
        entries = self.list()
        record = {"package_path": str(Path(package).resolve()), "registered_at": datetime.now(timezone.utc).isoformat(), "status": "APPROVED"}
        entries = [item for item in entries if item.get("package_path") != record["package_path"]]
        entries.append(record)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(entries, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return record

    def list(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            return payload if isinstance(payload, list) else []
        except (OSError, json.JSONDecodeError):
            return []
