#!/usr/bin/env python3
# ruff: noqa: E402
"""Explicitly migrate a validated legacy approval directory to v2.

Migration never promotes or approves a strategy. It preserves the legacy
approval decision and requires callers to supply the immutable adapter,
parameter, and risk-policy contracts that the legacy format did not contain.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from approval_package.package_validator import validate_package
from shared.strategy_package import CanonicalPackageBuild, build_canonical_package


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not value:
        raise ValueError(f"expected a non-empty JSON object: {path}")
    return value


def migrate_legacy_package(
    legacy_directory: Path | str,
    output: Path | str,
    *,
    adapter_id: str,
    adapter_version: str,
    parameters: dict[str, Any],
    risk_policy: dict[str, Any],
    legacy_signing_key: str,
    canonical_signing_key: str,
) -> CanonicalPackageBuild:
    legacy = Path(legacy_directory)
    result = validate_package(legacy, signing_key=legacy_signing_key)
    result.require_valid()
    status = json.loads((legacy / "approval_status.json").read_text(encoding="utf-8"))
    spec_bytes = (legacy / "strategy_spec.yaml").read_bytes()
    spec = yaml.safe_load(spec_bytes) or {}
    strategy_id = str(status.get("strategy_id") or spec.get("strategy_id") or "").strip()
    strategy_version = str(status.get("strategy_version") or spec.get("version") or "").strip()
    if not strategy_id or not strategy_version:
        raise ValueError("legacy package must identify strategy_id and version")

    evidence_files = sorted(
        path for path in legacy.iterdir() if path.is_file() and path.name not in {"signature.txt", "approval_status.json", "strategy_spec.yaml"}
    )
    evidence = {
        "legacy_evidence": {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in evidence_files
        }
    }
    approval = {
        "decision": str(status.get("approval_status", "")).upper(),
        "approved_at": status.get("approved_at", ""),
        "expires_at": status.get("expires_at", ""),
        "revoked": False,
        "authority": "legacy-package-migration",
    }
    provenance = {
        "source_format": "legacy-approval-directory/v1",
        "source_path": str(legacy),
        "source_files": {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(legacy.iterdir())
            if path.is_file()
        },
        "migration_is_approval": False,
    }
    return build_canonical_package(
        output,
        strategy_id=strategy_id,
        strategy_version=strategy_version,
        adapter_id=adapter_id,
        adapter_version=adapter_version,
        strategy_spec=spec_bytes,
        parameters=parameters,
        risk_policy=risk_policy,
        evidence=evidence,
        approval=approval,
        signing_key=canonical_signing_key,
        provenance=provenance,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("legacy_directory", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--adapter-id", required=True)
    parser.add_argument("--adapter-version", required=True)
    parser.add_argument("--parameters-json", type=Path, required=True)
    parser.add_argument("--risk-policy-json", type=Path, required=True)
    args = parser.parse_args()
    build = migrate_legacy_package(
        args.legacy_directory,
        args.output,
        adapter_id=args.adapter_id,
        adapter_version=args.adapter_version,
        parameters=_read_object(args.parameters_json),
        risk_policy=_read_object(args.risk_policy_json),
        legacy_signing_key=os.getenv("STRATEGY_PACKAGE_SIGNING_KEY", ""),
        canonical_signing_key=os.getenv("SVOS_PACKAGE_SIGNING_PRIVATE_KEY", ""),
    )
    print(json.dumps({"archive": build.archive_path, "archive_sha256": build.archive_sha256, "package_id": build.package_id}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
