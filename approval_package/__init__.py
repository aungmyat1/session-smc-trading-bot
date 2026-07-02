"""Immutable approval package contract shared across the system boundary."""

from approval_package.package_builder import build_approval_package
from approval_package.package_validator import PackageValidationResult, validate_package

__all__ = ["PackageValidationResult", "build_approval_package", "validate_package"]
