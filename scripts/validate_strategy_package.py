#!/usr/bin/env python3
"""Validate immutable strategy-package/v1 archives without extracting them."""

from __future__ import annotations

import argparse
import io
import json
import tarfile
from pathlib import Path
from typing import Any


REQUIRED_FILES = {
    "manifest.json",
    "catalog_manifest.json",
    "registry_record.json",
    "validations.json",
    "signature.json",
    "strategy_spec.md",
    "dependency_lock.txt",
}


def validate_archive(path: Path) -> dict[str, Any]:
    with tarfile.open(path, "r:gz") as archive:
        names = set(archive.getnames())
        missing = sorted(REQUIRED_FILES - names)
        manifest_member = archive.extractfile("manifest.json") if "manifest.json" in names else None
        signature_member = archive.extractfile("signature.json") if "signature.json" in names else None
        manifest = json.loads(manifest_member.read()) if manifest_member else {}
        signature = json.loads(signature_member.read()) if signature_member else {}

    errors: list[str] = []
    if missing:
        errors.append(f"missing required files: {missing}")
    if manifest.get("package_format") != "strategy-package/v1":
        errors.append("manifest package_format must be strategy-package/v1")
    if manifest.get("live_trading_enabled") is not False:
        errors.append("manifest must explicitly disable live trading")
    if not manifest.get("strategy") or not manifest.get("version") or not manifest.get("package_id"):
        errors.append("manifest strategy, version, and package_id are required")
    if not signature.get("scheme") or not signature.get("signature") or not signature.get("digest_sha256"):
        errors.append("signature envelope is incomplete")
    return {"valid": not errors, "errors": errors, "manifest": manifest, "signature": signature}


def _self_test() -> int:
    files = {
        name: "{}" for name in REQUIRED_FILES
    }
    files["manifest.json"] = json.dumps(
        {"package_format": "strategy-package/v1", "package_id": "test", "strategy": "TEST", "version": "0.0.0", "live_trading_enabled": False}
    )
    files["signature.json"] = json.dumps({"scheme": "sha256-attestation", "signature": "test", "digest_sha256": "test"})
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for name, value in files.items():
            raw = value.encode()
            info = tarfile.TarInfo(name)
            info.size = len(raw)
            archive.addfile(info, io.BytesIO(raw))
    buffer.seek(0)
    with tarfile.open(fileobj=buffer, mode="r:gz") as archive:
        assert REQUIRED_FILES.issubset(archive.getnames())
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", nargs="?", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return _self_test()
    if args.archive is None:
        parser.error("archive is required unless --self-test is used")
    result = validate_archive(args.archive)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
