from __future__ import annotations

from pathlib import Path


def default_catalog_path(root: Path | str) -> Path:
    return Path(root) / "config" / "strategy_catalog.yaml"


def resolve_catalog_path(path: Path | str | None, *, root: Path | str) -> Path:
    if path is not None:
        return Path(path)
    return default_catalog_path(root)
