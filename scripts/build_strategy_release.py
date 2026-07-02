#!/usr/bin/env python3
"""Build release assets for one approved strategy version."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from svos.deployment.service import DeploymentStatusService


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strategy", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()

    service = DeploymentStatusService(root=args.root)
    detail = service.strategy_version_detail(args.strategy, args.version)
    package = detail["package"]
    record = detail["record"]
    if not package.get("approved"):
        raise SystemExit("refusing release: strategy version is not approved")
    if record.get("current_stage") != "PRODUCTION_APPROVAL":
        raise SystemExit("refusing release: strategy is not at PRODUCTION_APPROVAL")

    deployment = service.create_deployment(strategy=args.strategy, version=args.version, target="production-disabled", actor="github-actions")
    args.output.mkdir(parents=True, exist_ok=True)
    archive = args.output / f"{args.strategy}-{args.version}.tar.gz"
    shutil.copy2(Path(package["archive_path"]), archive)
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    (args.output / f"{archive.name}.sha256").write_text(f"{checksum}  {archive.name}\n", encoding="utf-8")
    shutil.copy2(Path(package["manifest_path"]), args.output / "manifest.json")
    signature_path = Path(package["manifest_path"]).with_name("signature.json")
    shutil.copy2(signature_path, args.output / "signature.json")
    (args.output / "deployment.json").write_text(json.dumps(deployment, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (args.output / "release-notes.md").write_text(
        f"# {args.strategy} {args.version}\n\n"
        f"- Package ID: `{package['package_id']}`\n"
        f"- SHA-256: `{checksum}`\n"
        f"- Signature: `{package['signature_scheme']}`\n"
        f"- Deployment ID: `{deployment['deployment_id']}`\n"
        "- Activation policy: `production-disabled`\n",
        encoding="utf-8",
    )
    print(json.dumps({"archive": str(archive), "sha256": checksum, "deployment_id": deployment["deployment_id"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
