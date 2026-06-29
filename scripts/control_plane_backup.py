#!/usr/bin/env python3
# ruff: noqa: E402
"""Encrypted PostgreSQL backup/restore for the SVOS control plane.

Credentials are supplied to libpq through the child environment, never command
arguments. Restore is destructive and requires an exact confirmation token.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy.engine import make_url

from db.runtime import resolve_database_url


def _libpq_environment(database_url: str) -> dict[str, str]:
    url = make_url(database_url)
    env = dict(os.environ)
    values = {
        "PGHOST": url.host,
        "PGPORT": str(url.port or 5432),
        "PGUSER": url.username,
        "PGPASSWORD": url.password,
        "PGDATABASE": url.database,
    }
    env.update({key: value for key, value in values.items() if value})
    return env


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _passphrase_file(passphrase: str, directory: Path) -> Path:
    handle = tempfile.NamedTemporaryFile("w", dir=directory, prefix=".passphrase-", delete=False)
    try:
        handle.write(passphrase)
        handle.flush()
        os.fsync(handle.fileno())
    finally:
        handle.close()
    path = Path(handle.name)
    path.chmod(0o600)
    return path


def backup(database_url: str, output: Path, passphrase: str) -> Path:
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="svos-backup-") as temporary_dir:
        temporary = Path(temporary_dir)
        dump = temporary / "control-plane.dump"
        subprocess.run(
            ["pg_dump", "--format=custom", "--no-owner", "--no-acl", "--file", str(dump)],
            env=_libpq_environment(database_url),
            check=True,
        )
        passphrase_path = _passphrase_file(passphrase, temporary)
        try:
            subprocess.run(
                [
                    "gpg", "--batch", "--yes", "--symmetric", "--cipher-algo", "AES256",
                    "--passphrase-file", str(passphrase_path), "--output", str(output), str(dump),
                ],
                check=True,
            )
        finally:
            passphrase_path.unlink(missing_ok=True)
    manifest = {
        "schema": "svos-control-plane-backup-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "artifact": output.name,
        "sha256": _sha256(output),
        "encrypted": True,
    }
    output.with_suffix(output.suffix + ".manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    output.chmod(0o400)
    return output


def restore(database_url: str, backup_path: Path, passphrase: str, confirm: str) -> None:
    if confirm != "CONFIRM-RESTORE-CONTROL-PLANE":
        raise PermissionError("restore requires CONFIRM-RESTORE-CONTROL-PLANE")
    backup_path = backup_path.resolve()
    manifest_path = backup_path.with_suffix(backup_path.suffix + ".manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("sha256") != _sha256(backup_path):
        raise RuntimeError("backup integrity verification failed")
    with tempfile.TemporaryDirectory(prefix="svos-restore-") as temporary_dir:
        temporary = Path(temporary_dir)
        dump = temporary / "control-plane.dump"
        passphrase_path = _passphrase_file(passphrase, temporary)
        try:
            subprocess.run(
                [
                    "gpg", "--batch", "--yes", "--decrypt", "--passphrase-file", str(passphrase_path),
                    "--output", str(dump), str(backup_path),
                ],
                check=True,
            )
        finally:
            passphrase_path.unlink(missing_ok=True)
        subprocess.run(
            ["pg_restore", "--clean", "--if-exists", "--no-owner", "--no-acl", "--exit-on-error", str(dump)],
            env=_libpq_environment(database_url),
            check=True,
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    backup_parser = subparsers.add_parser("backup")
    backup_parser.add_argument("output", type=Path)
    restore_parser = subparsers.add_parser("restore")
    restore_parser.add_argument("backup", type=Path)
    restore_parser.add_argument("--confirm", required=True)
    args = parser.parse_args()
    database_url = resolve_database_url()
    passphrase = os.getenv("SVOS_BACKUP_PASSPHRASE", "")
    if not database_url or not passphrase:
        raise SystemExit("DATABASE_URL and SVOS_BACKUP_PASSPHRASE are required")
    if args.command == "backup":
        backup(database_url, args.output, passphrase)
    else:
        restore(database_url, args.backup, passphrase, args.confirm)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
