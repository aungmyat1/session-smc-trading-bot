"""Production preflight verification for staged deployment packages."""

from __future__ import annotations

import hashlib
import json
import tarfile
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from shared.serialization import now_iso, read_json, write_json
from shared.strategy_package import REQUIRED_MEMBERS, validate_canonical_package
from shared.configuration.symbols import validate_symbol


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

    _REQUIRED_FILES = REQUIRED_MEMBERS

    def __init__(self, *, root: Path | str) -> None:
        self.root = Path(root)
        self.import_root = self.root / "data" / "production" / "imports"
        self.report_root = self.root / "reports" / "production_preflight"

    def verify_import(self, deployment_id: str) -> PreflightVerificationResult:
        import_state = self._load_import_state(deployment_id)
        archive_path = Path(str(import_state.get("staged_archive_path", "")))
        if not archive_path.exists():
            raise FileNotFoundError(archive_path)

        actual_sha = self._file_sha256(archive_path)
        expected_sha = str(import_state.get("archive_sha256", ""))
        names, _, _ = self._read_archive_metadata(archive_path)
        revocations = read_json(self.root / "data" / "production" / "revoked_packages.json", {})
        revoked_ids = set(revocations.get("package_ids", [])) if isinstance(revocations, dict) else set()
        canonical = validate_canonical_package(
            archive_path,
            signing_key=os.getenv("SVOS_PACKAGE_VERIFYING_PUBLIC_KEY", ""),
            expected_strategy_id=str(import_state.get("strategy", "")) or None,
            revoked_package_ids=revoked_ids,
        )
        symbol_checks = [validate_symbol(symbol, scope="execution") for symbol in canonical.manifest.get("symbols", [])]
        execution_symbols_allowed = bool(symbol_checks) and all(item.valid for item in symbol_checks)

        checks = [
            self._check("archive_exists", archive_path.exists(), f"archive={archive_path}"),
            self._check("archive_checksum_matches_import", actual_sha == expected_sha, f"expected={expected_sha} actual={actual_sha}"),
            self._check("required_files_present", self._REQUIRED_FILES.issubset(names), f"missing={sorted(self._REQUIRED_FILES - names)}"),
            self._check("canonical_package_verified", canonical.valid, "; ".join(canonical.reasons) or "strategy-package/v2 verified"),
            self._check("manifest_format", str(canonical.manifest.get("package_format", "")) == "strategy-package/v2", f"package_format={canonical.manifest.get('package_format', '')}"),
            self._check("manifest_live_disabled", canonical.manifest.get("live_trading_enabled") is False, f"live_trading_enabled={canonical.manifest.get('live_trading_enabled')}"),
            self._check("manifest_strategy_present", bool(str(canonical.manifest.get("strategy_id", "")).strip()), f"strategy={canonical.manifest.get('strategy_id', '')}"),
            self._check("manifest_version_present", bool(str(canonical.manifest.get("strategy_version", "")).strip()), f"version={canonical.manifest.get('strategy_version', '')}"),
            self._check("approval_current", canonical.approval.get("decision") == "APPROVED" and canonical.approval.get("revoked") is False, f"decision={canonical.approval.get('decision', '')} revoked={canonical.approval.get('revoked')}"),
            self._check("symbols_execution_enabled", execution_symbols_allowed, "; ".join(error for item in symbol_checks for error in item.errors) or "all package symbols are enabled for execution"),
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
            manifest=canonical.manifest,
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
        try:
            with tarfile.open(archive_path, "r:gz") as archive:
                names = set(archive.getnames())
                manifest = cls._read_json_member(archive, "manifest.json")
                signature = cls._read_json_member(archive, "signature.json")
            return names, manifest, signature
        except (OSError, tarfile.TarError):
            return set(), {}, {}

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
