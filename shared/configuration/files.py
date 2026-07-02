from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_yaml_mapping(path: Path | str, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
    """Load a YAML file and normalize non-mapping payloads to a mapping default."""

    file_path = Path(path)
    fallback = dict(default or {})
    if not file_path.exists():
        return fallback
    payload = yaml.safe_load(file_path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        return fallback
    return dict(payload)
