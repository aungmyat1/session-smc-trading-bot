"""Reproducible run manifest — records the complete provenance of a pipeline run.

Every replay, backtest, robustness, and virtual-demo run must attach a manifest
so results can be reproduced and invalidation can be detected automatically.

The manifest captures:
- git commit hash and dirty-tree indicator
- Python interpreter and dependency lock hash
- strategy and specification hashes
- dataset snapshot identity and row range
- configuration and policy hashes
- deterministic seed and UTC timestamps
- engine and service versions

A run without a valid manifest is BLOCKED and cannot produce qualifying evidence.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from shared.serialization import now_iso, stable_manifest_hash


@dataclass(slots=True)
class RunManifest:
    manifest_id: str
    service: str
    strategy: str
    created_at: str
    git_commit: str
    git_dirty: bool
    python_version: str
    lock_hash: str          # SHA-256 of requirements*.txt or poetry.lock
    strategy_spec_hash: str
    dataset_id: str
    dataset_hash: str       # SHA-256 of dataset snapshot if available
    config_hash: str
    parameters: dict[str, Any] = field(default_factory=dict)
    engine_version: str = "svos-v1"
    timezone: str = "UTC"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def is_reproducible(self) -> bool:
        return bool(self.git_commit and not self.git_dirty)


class RunManifestBuilder:
    """Builds and persists run manifests for pipeline stages."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.manifests_root = self.root / "data" / "svos" / "manifests"

    def build(
        self,
        *,
        service: str,
        strategy: str,
        dataset_id: str = "",
        dataset_path: Path | str | None = None,
        parameters: dict[str, Any] | None = None,
        spec_hash: str = "",
        config_hash: str = "",
    ) -> RunManifest:
        """Build a manifest for the current environment and persist it."""
        params = parameters or {}
        git_commit, git_dirty = _git_state(self.root)
        lock_hash = _lock_hash(self.root)
        dataset_hash = _file_hash(Path(dataset_path)) if dataset_path else ""

        payload = {
            "service": service,
            "strategy": strategy,
            "git_commit": git_commit,
            "git_dirty": git_dirty,
            "python_version": sys.version,
            "lock_hash": lock_hash,
            "strategy_spec_hash": spec_hash,
            "dataset_id": dataset_id,
            "dataset_hash": dataset_hash,
            "config_hash": config_hash,
            "parameters": params,
            "created_at": now_iso(),
        }
        manifest_id = stable_manifest_hash(payload)

        manifest = RunManifest(
            manifest_id=manifest_id,
            service=service,
            strategy=strategy,
            created_at=payload["created_at"],
            git_commit=git_commit,
            git_dirty=git_dirty,
            python_version=payload["python_version"],
            lock_hash=lock_hash,
            strategy_spec_hash=spec_hash,
            dataset_id=dataset_id,
            dataset_hash=dataset_hash,
            config_hash=config_hash,
            parameters=params,
        )

        self._persist(manifest)
        return manifest

    def _persist(self, manifest: RunManifest) -> None:
        dest = self.manifests_root / manifest.strategy / f"{manifest.manifest_id}.json"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(manifest.to_dict(), indent=2, sort_keys=True), encoding="utf-8")


# ── helpers ────────────────────────────────────────────────────────────────

def _git_state(root: Path) -> tuple[str, bool]:
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, stderr=subprocess.DEVNULL, text=True
        ).strip()
        dirty_out = subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=root, stderr=subprocess.DEVNULL, text=True
        ).strip()
        return commit, bool(dirty_out)
    except Exception:
        return "unknown", True


def _lock_hash(root: Path) -> str:
    for candidate in ("poetry.lock", "requirements-lock.txt", "requirements.txt"):
        path = root / candidate
        if path.exists():
            return _file_hash(path)
    return ""


def _file_hash(path: Path) -> str:
    if not path or not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()
