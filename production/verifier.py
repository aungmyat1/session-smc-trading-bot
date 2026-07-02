"""Production preflight verification for staged deployment packages."""

from __future__ import annotations

import hashlib
import json
import tarfile
import hmac
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from shared.serialization import now_iso, read_json, write_json
from infrastructure.google_cloud import GoogleCloudError, KMSAsymmetricAdapter


@dataclass(frozen=True, slots=True)
class PreflightVerificationResult:
    deployment_id: str
    strategy: str
    version: str
    verdict: str
    verified: bool
    checks: list[dict[str, Any]]
    manifest: dict[str, Any]
    archive_sha256: str
    verified_at: str
    json_report_path: str = ""
    json_report_id: str = ""
    markdown_report_path: str = ""
    markdown_report_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ProductionPreflightVerifier:
    """Verify a staged deployment package before any activation workflow exists."""

    _REQUIRED_FILES = frozenset(
        {
            "manifest.json",
            "catalog_manifest.json",
            "registry_record.json",
            "signature.json",
            "strategy_spec.md",
            "validations.json",
        }
    )

    def __init__(self, *, root: Path | str) -> None:
        self.root = Path(root)
        self.import_root = self.root / "data" / "production" / "imports"
        self.report_root = self.root / "reports" / "production_preflight"

    def verify_import(self, deployment_id: str) -> PreflightVerificationResult:
        import_state = self._load_import_state(deployment_id)
        archive_path = Path(str(import_state.get("staged_archive_path", "")))
        if not archive_path.exists():
            raise FileNotFoundError(archive_path)

        names, manifest, signature = self._read_archive_metadata(archive_path)
        actual_sha = self._file_sha256(archive_path)
        expected_sha = str(import_state.get("archive_sha256", ""))

        checks = [
            self._check("archive_exists", archive_path.exists(), f"archive={archive_path}"),
            self._check("archive_checksum_matches_import", actual_sha == expected_sha, f"expected={expected_sha} actual={actual_sha}"),
            self._check("required_files_present", self._REQUIRED_FILES.issubset(names), f"missing={sorted(self._REQUIRED_FILES - names)}"),
            self._check("manifest_format", str(manifest.get("package_format", "")) == "strategy-package/v1", f"package_format={manifest.get('package_format', '')}"),
            self._check("manifest_live_disabled", bool(manifest.get("live_trading_enabled", True)) is False, f"live_trading_enabled={manifest.get('live_trading_enabled')}"),
            self._check("manifest_strategy_present", bool(str(manifest.get("strategy", "")).strip()), f"strategy={manifest.get('strategy', '')}"),
            self._check("manifest_version_present", bool(str(manifest.get("version", "")).strip()), f"version={manifest.get('version', '')}"),
            self._check("signature_present", bool(str(signature.get("signature", "")).strip()), f"scheme={signature.get('scheme', '')}"),
            self._verify_signature(manifest, signature),
        ]

        verified = all(item["passed"] for item in checks)
        verdict = "READY_DISABLED" if verified else "BLOCKED"
        result = PreflightVerificationResult(
            deployment_id=deployment_id,
            strategy=str(import_state.get("strategy", "")),
            version=str(import_state.get("version", "")),
            verdict=verdict,
            verified=verified,
            checks=checks,
            manifest=manifest,
            archive_sha256=actual_sha,
            verified_at=now_iso(),
        )
        return self._write_result(deployment_id, result)

    def verification_status(self, deployment_id: str) -> dict[str, Any]:
        path = self.import_root / deployment_id / "preflight_verification.json"
        payload = read_json(path, {})
        if not payload:
            raise KeyError(f"preflight verification not found: {deployment_id}")
        return payload

    def _load_import_state(self, deployment_id: str) -> dict[str, Any]:
        path = self.import_root / deployment_id / "import_state.json"
        payload = read_json(path, {})
        if not payload:
            raise KeyError(f"import not found for deployment: {deployment_id}")
        return payload

    def _write_result(self, deployment_id: str, result: PreflightVerificationResult) -> PreflightVerificationResult:
        report_dir = self.report_root / deployment_id
        report_dir.mkdir(parents=True, exist_ok=True)
        verified_stamp = result.verified_at.replace(":", "").replace("+00:00", "Z")
        json_path = report_dir / f"preflight_{verified_stamp}.json"
        markdown_path = report_dir / f"preflight_{verified_stamp}.md"
        json_report_id = str(json_path.relative_to(self.root)).replace("/", "__")
        markdown_report_id = str(markdown_path.relative_to(self.root)).replace("/", "__")
        final_result = PreflightVerificationResult(
            deployment_id=result.deployment_id,
            strategy=result.strategy,
            version=result.version,
            verdict=result.verdict,
            verified=result.verified,
            checks=result.checks,
            manifest=result.manifest,
            archive_sha256=result.archive_sha256,
            verified_at=result.verified_at,
            json_report_path=str(json_path),
            json_report_id=json_report_id,
            markdown_report_path=str(markdown_path),
            markdown_report_id=markdown_report_id,
        )
        write_json(json_path, final_result.to_dict())
        markdown_path.write_text(self._markdown_report(final_result), encoding="utf-8")
        path = self.import_root / deployment_id / "preflight_verification.json"
        write_json(path, final_result.to_dict())
        return final_result

    @classmethod
    def _read_archive_metadata(cls, archive_path: Path) -> tuple[set[str], dict[str, Any], dict[str, Any]]:
        with tarfile.open(archive_path, "r:gz") as archive:
            names = set(archive.getnames())
            manifest = cls._read_json_member(archive, "manifest.json")
            signature = cls._read_json_member(archive, "signature.json")
        return names, manifest, signature

    @staticmethod
    def _read_json_member(archive: tarfile.TarFile, name: str) -> dict[str, Any]:
        try:
            member = archive.extractfile(name)
        except KeyError:
            return {}
        if member is None:
            return {}
        try:
            payload = json.loads(member.read().decode("utf-8"))
        except Exception:
            return {}
        return payload if isinstance(payload, dict) else {}

    @staticmethod
    def _file_sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _check(name: str, passed: bool, detail: str) -> dict[str, Any]:
        return {
            "name": name,
            "passed": passed,
            "detail": detail,
        }

    @classmethod
    def _verify_signature(cls, manifest: dict[str, Any], envelope: dict[str, Any]) -> dict[str, Any]:
        canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
        digest = hashlib.sha256(canonical).digest()
        digest_hex = digest.hex()
        scheme = str(envelope.get("scheme", ""))
        signature = str(envelope.get("signature", ""))
        recorded_digest = str(envelope.get("digest_sha256", ""))
        valid = recorded_digest == digest_hex
        if scheme == "sha256-attestation":
            valid = valid and hmac.compare_digest(signature, digest_hex)
        elif scheme == "hmac-sha256":
            key = os.getenv("SVOS_PACKAGE_SIGNING_KEY", "").encode("utf-8")
            valid = valid and bool(key) and hmac.compare_digest(signature, hmac.new(key, canonical, hashlib.sha256).hexdigest())
        elif scheme == "gcp-kms-asymmetric-sha256":
            key_ref = str(envelope.get("key_ref", ""))
            try:
                valid = valid and bool(key_ref) and KMSAsymmetricAdapter().verify_digest(key_ref, digest, signature)
            except GoogleCloudError as exc:
                return cls._check("signature_verified", False, f"scheme={scheme} verification_error={exc}")
        elif scheme == "gcp-kms-asymmetric-attestation":
            key_ref = str(envelope.get("key_ref", ""))
            expected = hashlib.sha256(f"{key_ref}:{digest_hex}".encode("utf-8")).hexdigest()
            valid = valid and hmac.compare_digest(signature, expected)
        else:
            valid = False
        return cls._check("signature_verified", valid, f"scheme={scheme} key_ref={envelope.get('key_ref', '')}")

    @staticmethod
    def _markdown_report(result: PreflightVerificationResult) -> str:
        lines = [
            "# Production Preflight Verification",
            "",
            f"- Deployment ID: `{result.deployment_id}`",
            f"- Strategy: `{result.strategy}`",
            f"- Version: `{result.version}`",
            f"- Verdict: `{result.verdict}`",
            f"- Verified: `{str(result.verified).lower()}`",
            f"- Archive SHA256: `{result.archive_sha256}`",
            f"- Verified At: `{result.verified_at}`",
            "",
            "## Checks",
            "",
        ]
        for check in result.checks:
            status = "PASS" if bool(check.get("passed")) else "FAIL"
            lines.append(f"- `{check.get('name', '')}`: **{status}** — {check.get('detail', '')}")
        lines.extend(
            [
                "",
                "## Manifest",
                "",
                "```json",
                json.dumps(result.manifest, indent=2, sort_keys=True),
                "```",
                "",
            ]
        )
        return "\n".join(lines)
