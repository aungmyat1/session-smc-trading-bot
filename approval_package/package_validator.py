from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from approval_package.package_builder import REQUIRED_EVIDENCE
from approval_package.package_signature import verify_files


@dataclass(frozen=True, slots=True)
class PackageValidationResult:
    valid: bool
    reasons: tuple[str, ...]
    package_path: str

    def require_valid(self) -> None:
        if not self.valid:
            raise PermissionError("approved package rejected: " + "; ".join(self.reasons))


def validate_package(path: Path | str, *, signing_key: str | None = None, now: datetime | None = None) -> PackageValidationResult:
    directory = Path(path)
    reasons: list[str] = []
    required = (*REQUIRED_EVIDENCE, "approval_status.json", "signature.txt")
    missing = [name for name in required if not (directory / name).is_file()]
    if missing:
        return PackageValidationResult(False, tuple(f"missing file: {name}" for name in missing), str(directory))
    try:
        status = json.loads((directory / "approval_status.json").read_text(encoding="utf-8"))
        summary = json.loads((directory / "validation_summary.json").read_text(encoding="utf-8"))
        envelope = json.loads((directory / "signature.txt").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return PackageValidationResult(False, (f"invalid package document: {exc}",), str(directory))
    if status.get("approval_status") != "APPROVED":
        reasons.append("approval_status is not APPROVED")
    try:
        expiry = datetime.fromisoformat(str(status["expires_at"]).replace("Z", "+00:00"))
        current = now or datetime.now(timezone.utc)
        if expiry <= current:
            reasons.append("package is expired")
    except (KeyError, ValueError, TypeError):
        reasons.append("expires_at is missing or invalid")
    if str(summary.get("risk_check", "")).upper() != "PASS":
        reasons.append("risk_check did not pass")
    if str(summary.get("validation", "")).upper() != "PASS":
        reasons.append("strategy validation did not pass")
    unsigned = {item.name: item.read_bytes() for item in directory.iterdir() if item.is_file() and item.name != "signature.txt"}
    if not verify_files(unsigned, envelope, signing_key):
        reasons.append("signature is invalid")
    return PackageValidationResult(not reasons, tuple(reasons), str(directory))
