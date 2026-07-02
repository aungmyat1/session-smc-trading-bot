from __future__ import annotations

from approval_package.package_validator import validate_package


def require_approved_package(path: str, *, signing_key: str | None = None) -> None:
    validate_package(path, signing_key=signing_key).require_valid()
