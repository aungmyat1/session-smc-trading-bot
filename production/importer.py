"""Production artifact import and staging service.

This module is intentionally read-only with respect to deployment metadata:
it consumes the append-only deployment contract emitted by the SVOS side and
stages an approved package locally for production verification.
"""

from __future__ import annotations

import hashlib
import os
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from shared.serialization import now_iso, read_json, write_json
from infrastructure.google_cloud import GCSArtifactAdapter


@dataclass(frozen=True, slots=True)
class ImportedDeploymentPackage:
    deployment_id: str
    strategy: str
    version: str
    status: str
    package_transport: str
    package_registry_uri: str
    staged_archive_path: str
    stage_root: str
    archive_sha256: str
    verified: bool
    imported_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class DeploymentImportService:
    """Fetch and stage a deployment package for production-side verification."""

    def __init__(self, *, root: Path | str) -> None:
        self.root = Path(root)
        self.deployment_root = self.root / "data" / "svos" / "deployment"
        self.import_root = self.root / "data" / "production" / "imports"

    def import_deployment(self, deployment_id: str) -> ImportedDeploymentPackage:
        deployment = self._load_deployment(deployment_id)
        source = self._resolve_source_path(deployment)
        expected_sha = str(deployment.get("package_sha256", ""))
        actual_sha = self._file_sha256(source)
        if expected_sha and actual_sha != expected_sha:
            raise ValueError(
                f"package checksum mismatch for {deployment_id}: expected {expected_sha}, got {actual_sha}"
            )

        stage_root = self.import_root / deployment_id
        stage_root.mkdir(parents=True, exist_ok=True)
        staged_archive = stage_root / Path(source).name
        shutil.copy2(source, staged_archive)
        staged_sha = self._file_sha256(staged_archive)
        verified = staged_sha == actual_sha and (not expected_sha or staged_sha == expected_sha)

        record = ImportedDeploymentPackage(
            deployment_id=str(deployment.get("deployment_id", deployment_id)),
            strategy=str(deployment.get("strategy", "")),
            version=str(deployment.get("version", "")),
            status=str(deployment.get("status", "")),
            package_transport=str(deployment.get("package_transport", "")),
            package_registry_uri=str(deployment.get("package_registry_uri", "")),
            staged_archive_path=str(staged_archive),
            stage_root=str(stage_root),
            archive_sha256=staged_sha,
            verified=verified,
            imported_at=now_iso(),
        )
        write_json(stage_root / "import_state.json", record.to_dict())
        return record

    def import_status(self, deployment_id: str) -> dict[str, Any]:
        state_path = self.import_root / deployment_id / "import_state.json"
        payload = read_json(state_path, {})
        if not payload:
            raise KeyError(f"import not found for deployment: {deployment_id}")
        return payload

    def _load_deployment(self, deployment_id: str) -> dict[str, Any]:
        state_path = self.deployment_root / "deployments" / deployment_id / "state.json"
        payload = read_json(state_path, {})
        if not payload:
            raise KeyError(f"deployment not found: {deployment_id}")
        return payload

    def _resolve_source_path(self, deployment: dict[str, Any]) -> Path:
        transport = str(deployment.get("package_transport", "local"))
        registry_uri = str(deployment.get("package_registry_uri", ""))
        local_path = str(deployment.get("package_path", ""))
        if transport == "local":
            path = Path(local_path)
            if not path.exists():
                raise FileNotFoundError(path)
            return path
        if transport == "gcs":
            if not registry_uri.startswith("gs://"):
                raise ValueError(f"invalid gcs registry uri: {registry_uri}")
            if os.getenv("SVOS_CLOUD_ADAPTER", "mirror").strip().lower() == "real":
                destination = self.import_root / ".downloads" / str(deployment.get("deployment_id", "pending")) / "strategy_package.tar.gz"
                GCSArtifactAdapter().download(
                    registry_uri,
                    destination,
                    expected_sha256=str(deployment.get("package_sha256", "")),
                )
                return destination
            mirror_root = Path(os.getenv("SVOS_GCS_MIRROR_ROOT", "").strip() or (self.root / "data" / "gcs_mirror"))
            bucket_and_key = registry_uri.removeprefix("gs://")
            path = mirror_root / bucket_and_key
            if not path.exists():
                raise FileNotFoundError(path)
            return path
        raise ValueError(f"unsupported package transport: {transport}")

    @staticmethod
    def _file_sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
