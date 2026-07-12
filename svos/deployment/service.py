from __future__ import annotations

import gzip
import hashlib
import hmac
import io
import json
import os
import shutil
import tarfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.strategy_registry import (
    get_current_strategy_manifest,
    get_current_strategy_name,
    get_strategy_manifest,
    get_strategy_spec_path,
    get_strategy_spec_text,
)
from shared.serialization import append_jsonl, now_iso, read_json, read_jsonl, stable_manifest_hash, write_json
from svos.adapters.artifacts import FilesystemArtifactStore
from infrastructure.google_cloud import GCSArtifactAdapter, KMSAsymmetricAdapter
from svos.governance.service import GovernanceService
from svos.governance.snapshot import compute_strategy_governance_snapshot
from svos.registry.service import StrategyRegistryService
from shared.strategy_package import build_canonical_package
from shared.configuration.symbols import validate_symbol


@dataclass(frozen=True, slots=True)
class SignatureEnvelope:
    scheme: str
    signature: str
    key_ref: str = ""
    digest_sha256: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "scheme": self.scheme,
            "signature": self.signature,
            "key_ref": self.key_ref,
            "digest_sha256": self.digest_sha256,
        }


@dataclass(frozen=True, slots=True)
class PublishedArtifact:
    transport: str
    registry_uri: str
    mirror_path: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "transport": self.transport,
            "registry_uri": self.registry_uri,
            "mirror_path": self.mirror_path,
        }


class DeploymentStatusService:
    """Read and write deployment state over the SVOS registry and immutable artifacts."""

    def __init__(self, *, root: Path | str, catalog_path: Path | str | None = None) -> None:
        self.root = Path(root)
        self.catalog_path = Path(catalog_path) if catalog_path is not None else self.root / "config" / "strategy_catalog.yaml"
        self.registry = StrategyRegistryService(root=self.root, catalog_path=self.catalog_path)
        self.governance = GovernanceService(root=self.root, registry=self.registry)
        self.deployment_root = self.root / "data" / "svos" / "deployment"
        self.package_artifacts = FilesystemArtifactStore(self.deployment_root / "artifacts")
        self.report_artifacts = FilesystemArtifactStore(self.deployment_root / "report_artifacts")

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
            "package_transport": self._transport_mode(),
            "signing_mode": self._signing_mode(),
        }

    def latest_strategy_version(self, strategy: str) -> dict[str, Any]:
        record = self.registry.ensure_strategy(strategy)
        return self.strategy_version_detail(strategy, record.latest_version)

    def strategy_version_detail(self, strategy: str, version: str) -> dict[str, Any]:
        version_record = self._resolve_version(strategy, version)
        package = self._find_package(strategy, version)
        if package is None:
            package = self.build_strategy_package(strategy, version=version, actor="deployment-api")
        validations = self.validation_history(strategy, version)
        return {
            "strategy": strategy,
            "version": version_record.get("version", version),
            "version_id": version_record.get("version_id", ""),
            "created_at": version_record.get("created_at", ""),
            "actor": version_record.get("actor", ""),
            "reason": version_record.get("reason", ""),
            "manifest": dict(version_record.get("manifest", {})),
            "record": self.registry.get_strategy_record(strategy).to_dict(),
            "validation_count": len(validations),
            "validations": validations,
            "package": package,
        }

    def validation_history(self, strategy: str, version: str) -> list[dict[str, Any]]:
        version_record = self._resolve_version(strategy, version)
        version_id = str(version_record.get("version_id", ""))
        items: list[dict[str, Any]] = []

        for evidence in self.registry.evidence(strategy):
            metadata = evidence.get("metadata", {}) if isinstance(evidence.get("metadata"), dict) else {}
            evidence_version = str(metadata.get("strategy_version", ""))
            evidence_version_id = str(metadata.get("current_version_id", ""))
            if evidence_version == version or evidence_version_id == version_id:
                items.append(
                    {
                        "kind": "evidence",
                        "stage": str(evidence.get("stage", "")),
                        "status": str(evidence.get("status", "")),
                        "service": str(evidence.get("service", "")),
                        "report_type": str(evidence.get("report_type", "")),
                        "artifact_path": str(evidence.get("artifact_path", "")),
                        "artifact_hash": str(evidence.get("artifact_hash", "")),
                        "recorded_at": str(evidence.get("recorded_at", "")),
                        "evidence_id": str(evidence.get("evidence_id", "")),
                        "metadata": metadata,
                    }
                )

        approval = self._latest_approval_package(strategy, version_id=version_id)
        if approval is not None:
            items.append(
                {
                    "kind": "approval_package",
                    "stage": "PRODUCTION_APPROVAL",
                    "status": str(approval.get("status", "")),
                    "service": "svos.pipeline",
                    "report_type": "approval_package.json",
                    "artifact_path": str(approval.get("_path", "")),
                    "artifact_hash": str(approval.get("manifest_hash", "")),
                    "recorded_at": str(approval.get("generated_at", "")),
                    "evidence_id": "",
                    "metadata": {
                        "version_id": version_id,
                        "evidence_ids": approval.get("evidence_ids", {}),
                    },
                }
            )

        items.sort(key=lambda item: str(item.get("recorded_at", "")))
        return items

    def build_strategy_package(self, strategy: str, *, version: str | None = None, actor: str = "system") -> dict[str, Any]:
        version_record = self._resolve_version(strategy, version)
        version_label = str(version_record.get("version", ""))
        existing = self._find_package(strategy, version_label)
        if existing is not None:
            return existing

        manifest = dict(version_record.get("manifest", {}))
        record = self.registry.get_strategy_record(strategy).to_dict()
        validations = self.validation_history(strategy, version_label)
        version_id = str(version_record.get("version_id", ""))
        if manifest.get("approved") is not True or record.get("current_stage") != "PRODUCTION_APPROVAL":
            raise PermissionError("canonical package requires governance approval at PRODUCTION_APPROVAL")
        spec_path = get_strategy_spec_path(strategy, self.catalog_path)
        spec_text = get_strategy_spec_text(strategy, self.catalog_path) or ""
        source_manifest_hash = stable_manifest_hash(
            {"strategy": strategy, "version": version_label, "manifest": manifest}
        )
        approval = dict(manifest.get("approval", {}) or {})
        if not approval:
            approval = {
                "decision": "APPROVED" if manifest.get("approved") is True else "REJECTED",
                "approved_at": manifest.get("approved_at", version_record.get("created_at", "")),
                "expires_at": manifest.get("approval_expires_at", ""),
                "revoked": bool(manifest.get("revoked", False)),
                "authority": "svos-governance",
            }
        parameters = dict(manifest.get("parameters", {}) or {}) or {
            "symbols": list(manifest.get("symbols", []) or []),
            "timeframes": list(manifest.get("timeframes", []) or []),
        }
        parameters.setdefault("symbols", list(manifest.get("symbols", []) or []))
        for symbol in parameters["symbols"]:
            validation = validate_symbol(symbol, scope="execution")
            if not validation.valid:
                raise ValueError("; ".join(validation.errors))
        risk_policy = dict(manifest.get("risk_policy", {}) or {}) or {
            "policy_id": "catalog-requirements",
            "requirements": dict(manifest.get("requirements", {}) or {}),
            "live_trading_enabled": False,
        }
        evidence_records = validations or list(manifest.get("evidence", []) or [])
        if not evidence_records:
            raise ValueError("canonical package requires explicit qualification evidence")
        evidence_manifest = {
            "records": evidence_records,
            "source_manifest_hash": source_manifest_hash,
        }
        governance_snapshot = {
            "strategies": {
                strategy: compute_strategy_governance_snapshot(self.registry, self.governance, strategy)
            }
        }
        signing_key = os.getenv("SVOS_PACKAGE_SIGNING_PRIVATE_KEY", "")
        temporary_archive = self.deployment_root / "packages" / strategy / version_label / ".canonical-package.tmp.tar.gz"
        build = build_canonical_package(
            temporary_archive,
            strategy_id=strategy,
            strategy_version=version_label,
            adapter_id=str(manifest.get("adapter_id", strategy)),
            adapter_version=str(manifest.get("adapter_version", version_label)),
            strategy_spec=spec_text,
            parameters=parameters,
            risk_policy=risk_policy,
            evidence=evidence_manifest,
            governance_snapshot=governance_snapshot,
            approval=approval,
            signing_key=signing_key,
            provenance={
                "source_format": "svos-registry-and-catalog",
                "source_manifest_hash": source_manifest_hash,
                "version_id": version_id,
                "built_by": actor,
                "specification_path": str(spec_path) if spec_path is not None else "",
            },
        )
        package_id = build.package_id
        package_manifest = build.manifest
        package_dir = self.deployment_root / "packages" / strategy / version_label / package_id
        package_dir.mkdir(parents=True, exist_ok=True)
        archive_path = package_dir / "strategy_package.tar.gz"
        temporary_archive.replace(archive_path)
        manifest_path = package_dir / "manifest.json"
        write_json(manifest_path, package_manifest)
        with tarfile.open(archive_path, "r:gz") as archive:
            signature_member = archive.extractfile("signature.json")
            signature_payload = json.loads(signature_member.read()) if signature_member is not None else {}
        write_json(package_dir / "signature.json", signature_payload)

        stored = self.package_artifacts.put(archive_path)
        published = self._publish_package_archive(
            strategy=strategy,
            version=version_label,
            package_id=package_id,
            archive_path=archive_path,
        )
        payload = {
            "package_format": "strategy-package/v2",
            "package_id": package_id,
            "strategy": strategy,
            "version": version_label,
            "version_id": version_id,
            "built_at": str(approval.get("approved_at", "")),
            "built_by": actor,
            "current_stage": record.get("current_stage", ""),
            "approved": bool(manifest.get("approved", False)),
            "source_manifest_hash": source_manifest_hash,
            "manifest_path": str(manifest_path),
            "archive_path": str(archive_path),
            "content_addressed_path": str(stored.path),
            "archive_sha256": stored.sha256,
            "archive_size_bytes": stored.size_bytes,
            "signature_scheme": str(signature_payload.get("scheme", "")),
            "signature_value": str(signature_payload.get("signature", "")),
            "signature_key_ref": "env:SVOS_PACKAGE_SIGNING_PRIVATE_KEY",
            "digest_sha256": str(signature_payload.get("digest_sha256", "")),
            "validation_count": len(validations),
            "live_trading_enabled": False,
            "transport": published.transport,
            "registry_uri": published.registry_uri,
            "mirror_path": published.mirror_path,
        }
        append_jsonl(self._packages_path(), payload)
        write_json(self._package_state_path(strategy, version_label), payload)
        return payload

    def create_deployment(
        self,
        *,
        strategy: str,
        version: str | None = None,
        target: str | None = None,
        actor: str = "system",
        notes: str = "",
    ) -> dict[str, Any]:
        version_record = self._resolve_version(strategy, version)
        version_label = str(version_record.get("version", ""))
        package = self.build_strategy_package(strategy, version=version_label, actor=actor)
        manifest = dict(version_record.get("manifest", {}))
        requested_at = now_iso()
        deployment_id = stable_manifest_hash(
            {
                "strategy": strategy,
                "version": version_label,
                "package_id": package["package_id"],
                "requested_at": requested_at,
                "actor": actor,
            }
        )
        deployment = {
            "deployment_id": deployment_id,
            "strategy": strategy,
            "version": version_label,
            "version_id": str(version_record.get("version_id", "")),
            "target": target or str(manifest.get("deployment_target", "paper") or "paper"),
            "requested_at": requested_at,
            "actor": actor,
            "notes": notes,
            "status": "READY_DISABLED",
            "live_trading_enabled": False,
            "package_id": package["package_id"],
            "package_sha256": package["archive_sha256"],
            "package_path": package["content_addressed_path"],
            "package_registry_uri": package["registry_uri"],
            "package_transport": package["transport"],
            "report_count": 0,
            "last_report_at": "",
        }
        append_jsonl(self._deployments_path(), deployment)
        write_json(self._deployment_state_path(deployment_id), deployment)
        return deployment

    def deployment_history(self, *, strategy: str = "") -> list[dict[str, Any]]:
        items = read_jsonl(self._deployments_path())
        if strategy:
            items = [item for item in items if item.get("strategy") == strategy]
        latest: dict[str, dict[str, Any]] = {}
        for item in items:
            deployment_id = str(item.get("deployment_id", ""))
            if deployment_id:
                latest[deployment_id] = read_json(self._deployment_state_path(deployment_id), item)
        return sorted(latest.values(), key=lambda item: str(item.get("requested_at", "")), reverse=True)

    def registry_inventory(self) -> dict[str, Any]:
        registry = self.registry.summary()
        deployments = self.deployment_history()
        rollbacks = read_jsonl(self._rollbacks_path())
        for strategy in registry["strategies"]:
            manifest = strategy.get("manifest", {})
            name = str(strategy.get("strategy", ""))
            strategy["supported_brokers"] = list(manifest.get("supported_brokers", manifest.get("brokers", [])) or [])
            strategy["supported_symbols"] = list(manifest.get("symbols", []) or [])
            strategy["deployments"] = [item for item in deployments if item.get("strategy") == name]
            strategy["rollbacks"] = [item for item in rollbacks if item.get("strategy") == name]
            strategy["release"] = dict(manifest.get("release", {}) or {})
        return {**registry, "deployment_count": len(deployments), "rollback_count": len(rollbacks)}

    def create_rollback(
        self,
        deployment_id: str,
        *,
        to_version: str,
        actor: str,
        reason: str,
    ) -> dict[str, Any]:
        source = self._load_deployment_state(deployment_id)
        if not reason.strip():
            raise ValueError("rollback reason is required")
        replacement = self.create_deployment(
            strategy=str(source["strategy"]),
            version=to_version,
            target=str(source.get("target", "production-disabled")),
            actor=actor,
            notes=f"rollback from {deployment_id}: {reason}",
        )
        record = {
            "rollback_id": stable_manifest_hash(
                {"source_deployment_id": deployment_id, "replacement_deployment_id": replacement["deployment_id"], "actor": actor}
            ),
            "strategy": source["strategy"],
            "from_version": source["version"],
            "to_version": to_version,
            "source_deployment_id": deployment_id,
            "replacement_deployment_id": replacement["deployment_id"],
            "actor": actor,
            "reason": reason,
            "requested_at": now_iso(),
            "status": "READY_DISABLED",
        }
        append_jsonl(self._rollbacks_path(), record)
        return record

    def record_deployment_report(
        self,
        deployment_id: str,
        *,
        status: str,
        actor: str = "system",
        summary: str = "",
        metadata: dict[str, Any] | None = None,
        artifact_path: str = "",
    ) -> dict[str, Any]:
        deployment = self._load_deployment_state(deployment_id)
        recorded_at = now_iso()
        artifact_hash = ""
        artifact_store_path = ""
        if artifact_path:
            source = Path(artifact_path)
            if not source.is_absolute():
                source = self.root / source
            if not source.exists():
                raise FileNotFoundError(source)
            stored = self.report_artifacts.put(source)
            artifact_hash = stored.sha256
            artifact_store_path = str(stored.path)

        report = {
            "report_id": stable_manifest_hash(
                {
                    "deployment_id": deployment_id,
                    "status": status,
                    "recorded_at": recorded_at,
                    "artifact_hash": artifact_hash,
                }
            ),
            "deployment_id": deployment_id,
            "strategy": deployment["strategy"],
            "version": deployment["version"],
            "status": status,
            "summary": summary,
            "actor": actor,
            "recorded_at": recorded_at,
            "artifact_path": artifact_path,
            "artifact_store_path": artifact_store_path,
            "artifact_hash": artifact_hash,
            "metadata": metadata or {},
        }
        append_jsonl(self._deployment_reports_path(), report)
        deployment["status"] = status
        deployment["last_report_at"] = recorded_at
        deployment["report_count"] = int(deployment.get("report_count", 0)) + 1
        write_json(self._deployment_state_path(deployment_id), deployment)
        return report

    def deployment_status(self, deployment_id: str) -> dict[str, Any]:
        deployment = self._load_deployment_state(deployment_id)
        reports = [item for item in read_jsonl(self._deployment_reports_path()) if item.get("deployment_id") == deployment_id]
        return {
            **deployment,
            "reports": reports,
        }

    def _packages_path(self) -> Path:
        return self.deployment_root / "packages.jsonl"

    def _deployments_path(self) -> Path:
        return self.deployment_root / "deployments.jsonl"

    def _deployment_reports_path(self) -> Path:
        return self.deployment_root / "deployment_reports.jsonl"

    def _rollbacks_path(self) -> Path:
        return self.deployment_root / "rollbacks.jsonl"

    def _package_state_path(self, strategy: str, version: str) -> Path:
        return self.deployment_root / "packages" / strategy / version / "state.json"

    def _deployment_state_path(self, deployment_id: str) -> Path:
        return self.deployment_root / "deployments" / deployment_id / "state.json"

    def _load_deployment_state(self, deployment_id: str) -> dict[str, Any]:
        state = read_json(self._deployment_state_path(deployment_id), {})
        if not state:
            raise KeyError(f"deployment not found: {deployment_id}")
        return state

    def _resolve_version(self, strategy: str, version: str | None) -> dict[str, Any]:
        self.registry.ensure_strategy(strategy)
        versions = self.registry.versions(strategy)
        if not versions:
            raise KeyError(f"no versions registered for strategy: {strategy}")
        if version is None:
            return versions[-1]
        for item in reversed(versions):
            if str(item.get("version", "")) == version:
                return item
        manifest = get_strategy_manifest(strategy, self.catalog_path)
        if manifest is None:
            raise KeyError(f"strategy not found in catalog: {strategy}")
        if str(manifest.get("version", "")) == version:
            return self.registry.record_version(strategy, manifest=manifest, actor="deployment", reason="catalog version snapshot").to_dict()
        raise KeyError(f"version not found for strategy {strategy}: {version}")

    def _find_package(self, strategy: str, version: str) -> dict[str, Any] | None:
        for item in reversed(read_jsonl(self._packages_path())):
            if (
                item.get("strategy") == strategy
                and item.get("version") == version
                and item.get("package_format") == "strategy-package/v2"
            ):
                return item
        return None

    def _latest_approval_package(self, strategy: str, *, version_id: str) -> dict[str, Any] | None:
        approvals_dir = self.root / "data" / "svos" / "approvals" / strategy
        if not approvals_dir.exists():
            return None
        candidates = sorted(approvals_dir.glob("approval_*.json"))
        for candidate in reversed(candidates):
            payload = read_json(candidate, {})
            if payload and str(payload.get("version_id", "")) == version_id:
                payload["_path"] = str(candidate)
                return payload
        return None

    def _dependency_lock_payload(self) -> str:
        candidates = [
            self.root / "requirements-lock.txt",
            self.root / "requirements.txt",
            self.root / "poetry.lock",
            self.root / "pyproject.toml",
        ]
        for path in candidates:
            if path.exists() and path.is_file():
                return path.read_text(encoding="utf-8")
        return "# No dependency lock file available in repository root.\n"

    def _sign_payload(self, payload: dict[str, Any]) -> SignatureEnvelope:
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        digest = hashlib.sha256(canonical).hexdigest()
        mode = self._signing_mode()
        if mode == "gcp-kms-asymmetric":
            key_ref = os.getenv("SVOS_KMS_KEY_VERSION", "").strip()
            if key_ref and os.getenv("SVOS_CLOUD_ADAPTER", "mirror").strip().lower() == "real":
                signature = KMSAsymmetricAdapter().sign_digest(key_ref, bytes.fromhex(digest))
                return SignatureEnvelope(
                    scheme="gcp-kms-asymmetric-sha256",
                    signature=signature,
                    key_ref=key_ref,
                    digest_sha256=digest,
                )
            if key_ref:
                signature = hashlib.sha256(f"{key_ref}:{digest}".encode("utf-8")).hexdigest()
                return SignatureEnvelope(
                    scheme="gcp-kms-asymmetric-attestation",
                    signature=signature,
                    key_ref=key_ref,
                    digest_sha256=digest,
                )
            return SignatureEnvelope(
                scheme="gcp-kms-asymmetric-dry-run",
                signature=digest,
                key_ref="",
                digest_sha256=digest,
            )
        key = os.getenv("SVOS_PACKAGE_SIGNING_KEY", "").encode("utf-8")
        if mode == "hmac-sha256" and key:
            signature = hmac.new(key, canonical, hashlib.sha256).hexdigest()
            return SignatureEnvelope(
                scheme="hmac-sha256",
                signature=signature,
                key_ref="env:SVOS_PACKAGE_SIGNING_KEY",
                digest_sha256=digest,
            )
        return SignatureEnvelope(
            scheme="sha256-attestation",
            signature=digest,
            key_ref="",
            digest_sha256=digest,
        )

    def _transport_mode(self) -> str:
        mode = os.getenv("SVOS_PACKAGE_TRANSPORT", "local").strip().lower()
        return mode if mode in {"local", "gcs"} else "local"

    def _signing_mode(self) -> str:
        mode = os.getenv("SVOS_PACKAGE_SIGNING_MODE", "").strip().lower()
        if mode in {"hmac-sha256", "gcp-kms-asymmetric", "sha256-attestation"}:
            return mode
        if os.getenv("SVOS_KMS_KEY_VERSION", "").strip():
            return "gcp-kms-asymmetric"
        if os.getenv("SVOS_PACKAGE_SIGNING_KEY", "").strip():
            return "hmac-sha256"
        return "sha256-attestation"

    def _publish_package_archive(
        self,
        *,
        strategy: str,
        version: str,
        package_id: str,
        archive_path: Path,
    ) -> PublishedArtifact:
        mode = self._transport_mode()
        if mode == "gcs":
            bucket = os.getenv("SVOS_GCS_BUCKET", "").strip() or "svos-artifacts"
            prefix = os.getenv("SVOS_GCS_PREFIX", "strategy-packages").strip().strip("/")
            object_name = "/".join(part for part in [prefix, strategy, version, package_id, archive_path.name] if part)
            registry_uri = f"gs://{bucket}/{object_name}"
            mirror_root = os.getenv("SVOS_GCS_MIRROR_ROOT", "").strip()
            if os.getenv("SVOS_CLOUD_ADAPTER", "mirror").strip().lower() == "real":
                archive_sha256 = hashlib.sha256(archive_path.read_bytes()).hexdigest()
                GCSArtifactAdapter().upload(archive_path, registry_uri, sha256=archive_sha256)
                mirror = ""
            elif mirror_root:
                mirror_path = Path(mirror_root) / bucket / object_name
                mirror_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(archive_path, mirror_path)
                mirror = str(mirror_path)
            else:
                mirror = ""
            return PublishedArtifact(transport="gcs", registry_uri=registry_uri, mirror_path=mirror)
        return PublishedArtifact(
            transport="local",
            registry_uri=str(archive_path),
            mirror_path=str(archive_path),
        )

    def _build_deterministic_archive(self, files: dict[str, str]) -> bytes:
        raw = io.BytesIO()
        with gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as gz:
            with tarfile.open(fileobj=gz, mode="w") as tar:
                for name in sorted(files):
                    data = files[name].encode("utf-8")
                    info = tarfile.TarInfo(name=name)
                    info.size = len(data)
                    info.mode = 0o444
                    info.mtime = 0
                    info.uid = 0
                    info.gid = 0
                    info.uname = ""
                    info.gname = ""
                    tar.addfile(info, io.BytesIO(data))
        return raw.getvalue()
