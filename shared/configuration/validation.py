from __future__ import annotations

from pathlib import Path


def default_validation_config_path(root: Path | str) -> Path:
    return Path(root) / "config" / "validation.yaml"


def resolve_validation_config_path(path: Path | str | None, *, root: Path | str) -> Path:
    if path is not None:
        return Path(path)
    return default_validation_config_path(root)
