"""
Strategy Registry — central lookup for all registered strategies.

The in-memory registry keeps adapter instances for runtime use, while the
strategy catalog on disk acts as the source of truth for lifecycle state,
approval, and deployment metadata.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import yaml
except ImportError as exc:  # pragma: no cover - dependency exists in CI
    raise RuntimeError("PyYAML is required for the strategy catalog") from exc

from core.base_strategy import BaseStrategy

_registry: Dict[str, BaseStrategy] = {}
_LIFECYCLE_ORDER = {
    "draft": 0,
    "research": 1,
    "replay": 2,
    "backtest": 3,
    "walk_forward": 4,
    "shadow": 5,
    "demo": 6,
    "live": 7,
    "retired": 8,
}
_CATALOG_PATH = Path(__file__).resolve().parents[1] / "config" / "strategy_catalog.yaml"
_CURRENT_STRATEGY_KEY = "current_strategy"


class DirectCatalogMutationError(PermissionError):
    """Raised when legacy code attempts to mutate the catalog directly."""


def _normalize_name(name: str) -> str:
    return name.strip()


def _normalize_status(status: str | None) -> str:
    return (status or "draft").strip().lower()


def _catalog_payload(path: Path | None = None) -> dict[str, Any]:
    catalog_path = Path(path) if path is not None else _CATALOG_PATH
    if not catalog_path.exists():
        return {"strategies": {}}
    with catalog_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        return {"strategies": {}}
    data = dict(data)
    strategies = data.get("strategies", {})
    if not isinstance(strategies, dict):
        strategies = {}
    data["strategies"] = strategies
    return data


def _write_catalog(payload: dict[str, Any], path: Path | None = None) -> None:
    catalog_path = Path(path) if path is not None else _CATALOG_PATH
    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    with catalog_path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(payload, handle, sort_keys=False, allow_unicode=False)


def load_strategy_catalog(path: Path | str | None = None) -> dict[str, dict[str, Any]]:
    """Return the strategy catalog as a mapping keyed by strategy name."""
    payload = _catalog_payload(Path(path) if path is not None else None)
    strategies = payload["strategies"]
    return {
        _normalize_name(name): (entry if isinstance(entry, dict) else {})
        for name, entry in strategies.items()
    }


def get_strategy_manifest(name: str, path: Path | str | None = None) -> Optional[dict[str, Any]]:
    """Return the catalog entry for a strategy, or None if it is unknown."""
    return load_strategy_catalog(path).get(_normalize_name(name))


def list_catalog_strategies(path: Path | str | None = None) -> List[str]:
    """Return catalog strategy names sorted alphabetically."""
    return sorted(load_strategy_catalog(path).keys())


def get_backtest_script(name: str, path: Path | str | None = None) -> Optional[Path]:
    """Return the resolved backtest script path for a strategy, or None if not configured."""
    manifest = get_strategy_manifest(name, path)
    if not manifest:
        return None
    raw = manifest.get("backtest_script")
    if not raw:
        return None
    script_path = Path(str(raw))
    if script_path.is_absolute():
        return script_path
    catalog_path = Path(path) if path is not None else _CATALOG_PATH
    return catalog_path.parent.parent / script_path


def get_strategy_spec_path(name: str, path: Path | str | None = None) -> Optional[Path]:
    """Return the audited strategy spec path, if one is configured."""
    manifest = get_strategy_manifest(name, path)
    if not manifest:
        return None
    raw = manifest.get("strategy_spec_path")
    if not raw:
        return None
    spec_path = Path(str(raw))
    if spec_path.is_absolute():
        return spec_path
    catalog_path = Path(path) if path is not None else _CATALOG_PATH
    candidates = [catalog_path.parent, catalog_path.parent.parent]
    for base in candidates:
        candidate = base / spec_path
        if candidate.exists():
            return candidate
    return candidates[-1] / spec_path


def get_strategy_spec_text(name: str, path: Path | str | None = None) -> Optional[str]:
    """Return the strategy spec text from the catalog-specified document."""
    spec_path = get_strategy_spec_path(name, path)
    if spec_path is not None and spec_path.exists():
        return spec_path.read_text(encoding="utf-8")
    manifest = get_strategy_manifest(name, path)
    if manifest and manifest.get("description"):
        return str(manifest["description"])
    return None


def get_current_strategy_name(path: Path | str | None = None) -> Optional[str]:
    """Return the catalog's active strategy name, if one is set."""
    payload = _catalog_payload(Path(path) if path is not None else None)
    current = payload.get(_CURRENT_STRATEGY_KEY)
    if isinstance(current, str) and current.strip():
        return _normalize_name(current)
    for name, manifest in payload.get("strategies", {}).items():
        if isinstance(manifest, dict) and bool(manifest.get("current", False)):
            return _normalize_name(name)
    return None


def get_current_strategy_manifest(path: Path | str | None = None) -> Optional[dict[str, Any]]:
    """Return the active strategy manifest, if one is set."""
    current = get_current_strategy_name(path)
    if not current:
        return None
    return get_strategy_manifest(current, path)


def strategy_lifecycle_status(name: str, path: Path | str | None = None) -> str:
    """Return the normalized lifecycle status for a strategy."""
    manifest = get_strategy_manifest(name, path)
    if not manifest:
        return "draft"
    return _normalize_status(str(manifest.get("status", "draft")))


def strategy_lifecycle_rank(status: str) -> int:
    """Return an ordinal for comparing lifecycle states."""
    return _LIFECYCLE_ORDER.get(_normalize_status(status), -1)


def is_strategy_approved(name: str, path: Path | str | None = None) -> bool:
    """Return True when the catalog explicitly approves the strategy."""
    manifest = get_strategy_manifest(name, path)
    if not manifest:
        return False
    return bool(manifest.get("approved", False))


def can_deploy_strategy(
    name: str,
    target_stage: str = "demo",
    path: Path | str | None = None,
) -> bool:
    """
    Return True when a strategy is approved and has reached the requested stage.

    The target stage defaults to demo trading because that is the most common
    execution guard in this repository.
    """
    manifest = get_strategy_manifest(name, path)
    if not manifest:
        return False
    status = _normalize_status(str(manifest.get("status", "draft")))
    if status == "retired":
        return False
    if not bool(manifest.get("approved", False)):
        return False
    return strategy_lifecycle_rank(status) >= strategy_lifecycle_rank(target_stage)


def _update_strategy_projection(
    name: str,
    updates: dict[str, Any],
    path: Path | str | None = None,
) -> dict[str, Any]:
    """Internal compatibility projection writer used only by the registry."""
    catalog_path = Path(path) if path is not None else _CATALOG_PATH
    payload = _catalog_payload(catalog_path)
    strategies = payload.setdefault("strategies", {})
    manifest = strategies.get(name, {})
    if not isinstance(manifest, dict):
        manifest = {}
    manifest.update(updates)
    strategies[name] = manifest
    _write_catalog(payload, catalog_path)
    return manifest


def update_strategy_manifest(
    name: str,
    updates: dict[str, Any],
    path: Path | str | None = None,
) -> dict[str, Any]:
    """Reject legacy direct catalog mutation.

    Callers must submit lifecycle changes through ``GovernanceService``. This
    public shim remains temporarily so old integrations fail closed instead of
    importing a missing symbol and inventing another write path.
    """
    raise DirectCatalogMutationError(
        "Direct strategy-catalog mutation is disabled; use GovernanceService."
    )


def set_current_strategy(
    name: str,
    path: Path | str | None = None,
) -> dict[str, Any]:
    """Reject legacy current-strategy mutation."""
    raise DirectCatalogMutationError(
        "Direct current-strategy mutation is disabled; use GovernanceService."
    )


def promote_strategy_stage(
    name: str,
    next_stage: str,
    approved: Optional[bool] = None,
    path: Path | str | None = None,
) -> dict[str, Any]:
    """Reject legacy lifecycle promotion."""
    raise DirectCatalogMutationError(
        "Direct lifecycle promotion is disabled; use GovernanceService."
    )


def register_strategy(strategy: BaseStrategy) -> None:
    """Register a strategy instance under its name."""
    _registry[_normalize_name(strategy.name)] = strategy


def get_strategy(name: str) -> Optional[BaseStrategy]:
    """Return registered strategy by name, or None if not found."""
    return _registry.get(_normalize_name(name))


def list_strategies() -> List[str]:
    """Return sorted list of all registered strategy names."""
    return sorted(_registry.keys())


def clear_registry() -> None:
    """Clear all registrations — for testing only."""
    _registry.clear()
