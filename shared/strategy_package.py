"""Canonical strategy-package/v2 contract shared across the system boundary.

System 1 may build these archives. System 2 may verify and consume them. This
module contains no research, approval, broker, risk-execution, or trading logic.
"""

from __future__ import annotations

import gzip
import hashlib
import io
import json
import tarfile
import base64
import binascii
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

PACKAGE_FORMAT = "strategy-package/v2"
SIGNATURE_SCHEME = "ed25519"
REQUIRED_MEMBERS = frozenset(
    {
        "manifest.json",
        "strategy_spec.md",
        "parameters.json",
        "risk_policy.json",
        "evidence_manifest.json",
        "approval.json",
        "provenance.json",
        "signature.json",
    }
)
SIGNED_MEMBERS = REQUIRED_MEMBERS - {"signature.json"}


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, separators=(",", ": ")) + "\n").encode("utf-8")


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _parse_time(value: object) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _member_hashes(files: Mapping[str, bytes]) -> dict[str, str]:
    return {name: hashlib.sha256(files[name]).hexdigest() for name in sorted(files)}


def _archive_bytes(files: Mapping[str, bytes]) -> bytes:
    raw = io.BytesIO()
    with gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as compressed:
        with tarfile.open(fileobj=compressed, mode="w") as archive:
            for name in sorted(files):
                data = files[name]
                info = tarfile.TarInfo(name)
                info.size = len(data)
                info.mode = 0o444
                info.mtime = 0
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                archive.addfile(info, io.BytesIO(data))
    return raw.getvalue()


@dataclass(frozen=True, slots=True)
class CanonicalPackageBuild:
    archive_path: str
    archive_sha256: str
    package_id: str
    manifest: dict[str, Any]


@dataclass(frozen=True, slots=True)
class CanonicalPackageValidation:
    valid: bool
    reasons: tuple[str, ...]
    archive_path: str
    archive_sha256: str
    package_id: str
    manifest: dict[str, Any]
    approval: dict[str, Any]

    def require_valid(self) -> None:
        if not self.valid:
            raise PermissionError("canonical strategy package rejected: " + "; ".join(self.reasons))


def build_canonical_package(
    output: Path | str,
    *,
    strategy_id: str,
    strategy_version: str,
    adapter_id: str,
    adapter_version: str,
    strategy_spec: bytes | str,
    parameters: Mapping[str, Any],
    risk_policy: Mapping[str, Any],
    evidence: Mapping[str, Any],
    approval: Mapping[str, Any],
    signing_key: str,
    provenance: Mapping[str, Any] | None = None,
) -> CanonicalPackageBuild:
    """Build a deterministic canonical archive from already-approved evidence."""

    required_text = {
        "strategy_id": strategy_id,
        "strategy_version": strategy_version,
        "adapter_id": adapter_id,
        "adapter_version": adapter_version,
    }
    missing = [name for name, value in required_text.items() if not str(value).strip()]
    if missing:
        raise ValueError("missing canonical package identity: " + ", ".join(missing))
    if not signing_key:
        raise ValueError("canonical package signing key is required")
    if not parameters:
        raise ValueError("immutable strategy parameters are required")
    package_symbols = [str(value).strip().upper() for value in parameters.get("symbols", [])]
    if not package_symbols:
        raise ValueError("canonical package requires at least one immutable symbol")
    if not risk_policy:
        raise ValueError("risk policy is required")
    if not evidence:
        raise ValueError("evidence manifest is required")

    decision = str(approval.get("decision", "")).upper()
    if decision != "APPROVED":
        raise ValueError("canonical packages require an APPROVED decision")
    if approval.get("revoked") is not False:
        raise ValueError("canonical package approval must explicitly set revoked=false")
    approved_at = _parse_time(approval.get("approved_at"))
    expires_at = _parse_time(approval.get("expires_at"))
    if expires_at <= approved_at:
        raise ValueError("approval expiry must be after approval time")

    spec_bytes = strategy_spec.encode("utf-8") if isinstance(strategy_spec, str) else bytes(strategy_spec)
    semantic_files = {
        "strategy_spec.md": spec_bytes,
        "parameters.json": _json_bytes(dict(parameters)),
        "risk_policy.json": _json_bytes(dict(risk_policy)),
        "evidence_manifest.json": _json_bytes(dict(evidence)),
        "approval.json": _json_bytes(dict(approval)),
        "provenance.json": _json_bytes(dict(provenance or {"source_format": PACKAGE_FORMAT})),
    }
    semantic_hashes = _member_hashes(semantic_files)
    package_id = hashlib.sha256(
        _canonical_json(
            {
                "package_format": PACKAGE_FORMAT,
                "strategy_id": strategy_id,
                "strategy_version": strategy_version,
                "adapter_id": adapter_id,
                "adapter_version": adapter_version,
                "symbols": package_symbols,
                "members": semantic_hashes,
            }
        )
    ).hexdigest()
    manifest = {
        "package_format": PACKAGE_FORMAT,
        "package_id": package_id,
        "strategy_id": strategy_id,
        "strategy_version": strategy_version,
        "adapter_id": adapter_id,
        "adapter_version": adapter_version,
        "symbols": package_symbols,
        "live_trading_enabled": False,
        "members": semantic_hashes,
    }
    unsigned_files = {"manifest.json": _json_bytes(manifest), **semantic_files}
    signed_hashes = _member_hashes(unsigned_files)
    signed_digest = hashlib.sha256(_canonical_json(signed_hashes)).hexdigest()
    try:
        private_key = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(signing_key))
    except (ValueError, TypeError) as exc:
        raise ValueError("canonical package signing key must be a 32-byte Ed25519 private key encoded as hex") from exc
    signature = {
        "scheme": SIGNATURE_SCHEME,
        "digest_sha256": signed_digest,
        "signature": base64.b64encode(private_key.sign(signed_digest.encode("ascii"))).decode("ascii"),
        "members": signed_hashes,
    }
    all_files = {**unsigned_files, "signature.json": _json_bytes(signature)}
    archive = _archive_bytes(all_files)
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(archive)
    return CanonicalPackageBuild(str(path), hashlib.sha256(archive).hexdigest(), package_id, manifest)


def _read_archive(path: Path) -> tuple[dict[str, bytes], list[str]]:
    errors: list[str] = []
    files: dict[str, bytes] = {}
    try:
        with tarfile.open(path, "r:gz") as archive:
            names = archive.getnames()
            if len(names) != len(set(names)):
                errors.append("archive contains duplicate member names")
            unexpected = sorted(set(names) - REQUIRED_MEMBERS)
            missing = sorted(REQUIRED_MEMBERS - set(names))
            if missing:
                errors.append(f"missing required members: {missing}")
            if unexpected:
                errors.append(f"unexpected archive members: {unexpected}")
            for name in sorted(set(names) & REQUIRED_MEMBERS):
                member = archive.getmember(name)
                if not member.isfile() or Path(name).is_absolute() or ".." in Path(name).parts:
                    errors.append(f"unsafe archive member: {name}")
                    continue
                stream = archive.extractfile(member)
                files[name] = stream.read() if stream is not None else b""
    except (OSError, tarfile.TarError) as exc:
        errors.append(f"invalid canonical archive: {exc}")
    return files, errors


def validate_canonical_package(
    path: Path | str,
    *,
    signing_key: str,
    now: datetime | None = None,
    expected_strategy_id: str | None = None,
    expected_adapter_version: str | None = None,
    revoked_package_ids: set[str] | frozenset[str] = frozenset(),
) -> CanonicalPackageValidation:
    archive_path = Path(path)
    archive_hash = hashlib.sha256(archive_path.read_bytes()).hexdigest() if archive_path.is_file() else ""
    reasons: list[str] = []
    if not signing_key:
        reasons.append("canonical package signing key is required")
    files, archive_errors = _read_archive(archive_path)
    reasons.extend(archive_errors)

    def load_json(name: str) -> dict[str, Any]:
        try:
            value = json.loads(files[name])
            return value if isinstance(value, dict) else {}
        except (KeyError, json.JSONDecodeError, UnicodeDecodeError):
            reasons.append(f"invalid JSON member: {name}")
            return {}

    manifest = load_json("manifest.json")
    approval = load_json("approval.json")
    signature = load_json("signature.json")
    package_id = str(manifest.get("package_id", ""))

    if manifest.get("package_format") != PACKAGE_FORMAT:
        reasons.append(f"package_format must be {PACKAGE_FORMAT}")
    if manifest.get("live_trading_enabled") is not False:
        reasons.append("live_trading_enabled must be false")
    for key in ("package_id", "strategy_id", "strategy_version", "adapter_id", "adapter_version"):
        if not str(manifest.get(key, "")).strip():
            reasons.append(f"manifest field is required: {key}")
    if not isinstance(manifest.get("symbols"), list) or not manifest.get("symbols"):
        reasons.append("manifest symbols must be a non-empty list")
    if expected_strategy_id and manifest.get("strategy_id") != expected_strategy_id:
        reasons.append("strategy identity mismatch")
    if expected_adapter_version and manifest.get("adapter_version") != expected_adapter_version:
        reasons.append("adapter version mismatch")
    if package_id in revoked_package_ids:
        reasons.append("package is revoked")

    if set(files) >= SIGNED_MEMBERS:
        semantic_files = {name: files[name] for name in SIGNED_MEMBERS - {"manifest.json"}}
        semantic_hashes = _member_hashes(semantic_files)
        expected_id = hashlib.sha256(
            _canonical_json(
                {
                    "package_format": PACKAGE_FORMAT,
                    "strategy_id": manifest.get("strategy_id"),
                    "strategy_version": manifest.get("strategy_version"),
                    "adapter_id": manifest.get("adapter_id"),
                    "adapter_version": manifest.get("adapter_version"),
                    "symbols": manifest.get("symbols"),
                    "members": semantic_hashes,
                }
            )
        ).hexdigest()
        if manifest.get("members") != semantic_hashes:
            reasons.append("manifest member hashes do not match archive contents")
        if package_id != expected_id:
            reasons.append("package_id does not match canonical contents")
        signed_files = {name: files[name] for name in SIGNED_MEMBERS}
        signed_hashes = _member_hashes(signed_files)
        signed_digest = hashlib.sha256(_canonical_json(signed_hashes)).hexdigest()
        if signature.get("scheme") != SIGNATURE_SCHEME:
            reasons.append(f"signature scheme must be {SIGNATURE_SCHEME}")
        if signature.get("members") != signed_hashes or signature.get("digest_sha256") != signed_digest:
            reasons.append("signature member digest does not match archive contents")
        try:
            public_key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(signing_key))
            public_key.verify(base64.b64decode(str(signature.get("signature", "")), validate=True), signed_digest.encode("ascii"))
        except (ValueError, TypeError, binascii.Error, InvalidSignature):
            reasons.append("signature is invalid")

    if str(approval.get("decision", "")).upper() != "APPROVED":
        reasons.append("approval decision is not APPROVED")
    if approval.get("revoked") is not False:
        reasons.append("approval is revoked or missing revoked=false")
    try:
        approved_at = _parse_time(approval.get("approved_at"))
        expires_at = _parse_time(approval.get("expires_at"))
        current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        if expires_at <= approved_at:
            reasons.append("approval expiry is not after approval time")
        if expires_at <= current:
            reasons.append("package is expired")
    except (TypeError, ValueError):
        reasons.append("approval timestamps are missing or invalid")

    for name in ("parameters.json", "risk_policy.json", "evidence_manifest.json"):
        payload = load_json(name)
        if not payload:
            reasons.append(f"{name} must contain a non-empty object")

    return CanonicalPackageValidation(
        not reasons,
        tuple(dict.fromkeys(reasons)),
        str(archive_path),
        archive_hash,
        package_id,
        manifest,
        approval,
    )
