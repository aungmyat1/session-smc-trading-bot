from __future__ import annotations

from pathlib import Path
from typing import Any

from svos.adapters.artifacts import FilesystemArtifactStore
from svos.shared.support import now_iso, read_json, write_json


class StandardizedReportService:
    """Standardizes report metadata across stages without changing report content."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.index_path = self.root / "data" / "svos" / "reports" / "index.json"
        self.artifacts = FilesystemArtifactStore(self.root / "data" / "svos" / "artifacts")

    def register_artifact(
        self,
        *,
        strategy: str,
        stage: str,
        service: str,
        report_type: str,
        artifact_path: Path | str,
        status: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        path = Path(artifact_path)
        if not path.is_absolute():
            path = self.root / path
        stored = self.artifacts.put(path)
        artifact_hash = stored.sha256
        payload = {
            "report_id": f"{strategy}:{stage}:{service}:{report_type}:{artifact_hash[:12] or 'missing'}",
            "strategy": strategy,
            "stage": stage,
            "service": service,
            "report_type": report_type,
            "artifact_path": str(path),
            "content_addressed_path": str(stored.path),
            "size_bytes": stored.size_bytes,
            "artifact_hash": artifact_hash,
            "status": status,
            "recorded_at": now_iso(),
            "metadata": metadata or {},
        }
        index = read_json(self.index_path, {"reports": []})
        reports = list(index.get("reports", []))
        reports.append(payload)
        index["reports"] = reports
        index["generated_at"] = payload["recorded_at"]
        write_json(self.index_path, index)
        return payload

    def index(self) -> dict[str, Any]:
        return read_json(self.index_path, {"generated_at": "", "reports": []})
