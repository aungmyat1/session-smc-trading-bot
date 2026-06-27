from __future__ import annotations

import os
import subprocess
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any


@lru_cache(maxsize=1)
def _git_sha(root: str | None = None) -> str:
    try:
        cwd = Path(root) if root else Path(__file__).resolve().parents[1]
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            check=False,
        )
        sha = (out.stdout or "").strip()
        return sha or os.environ.get("GIT_SHA", "unknown")
    except Exception:
        return os.environ.get("GIT_SHA", "unknown")


@lru_cache(maxsize=1)
def _git_release(root: str | None = None) -> dict[str, str]:
    try:
        cwd = Path(root) if root else Path(__file__).resolve().parents[1]
        out = subprocess.run(
            ["git", "describe", "--tags", "--dirty", "--always"],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            check=False,
        )
        tag = (out.stdout or "").strip()
        return {
            "release_tag": tag or os.environ.get("RELEASE_TAG", "unknown"),
            "release_dirty": "dirty" if tag.endswith("-dirty") else "clean",
        }
    except Exception:
        return {
            "release_tag": os.environ.get("RELEASE_TAG", "unknown"),
            "release_dirty": os.environ.get("RELEASE_DIRTY", "unknown"),
        }


def build_release_metadata(root: str | None = None) -> dict[str, Any]:
    payload = {
        "code_version": _git_sha(root),
    }
    payload.update(_git_release(root))
    return payload


def build_lineage_metadata(
    *,
    source: str,
    strategy: str,
    strategy_version: str,
    artifact: str = "",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "source": source,
        "artifact": artifact,
        "strategy": strategy,
        "strategy_version": strategy_version,
        **build_release_metadata(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if extra:
        payload.update(extra)
    return payload
