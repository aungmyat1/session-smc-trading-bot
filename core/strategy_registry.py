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
    strategies = data.get("strategies", {})
    if not isinstance(strategies, dict):
        strategies = {}
    return {"strategies": strategies}


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


def update_strategy_manifest(
    name: str,
    updates: dict[str, Any],
    path: Path | str | None = None,
) -> dict[str, Any]:
    """Update a strategy manifest on disk and return the updated entry."""
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


def promote_strategy_stage(
    name: str,
    next_stage: str,
    approved: Optional[bool] = None,
    path: Path | str | None = None,
) -> dict[str, Any]:
    """Advance a strategy to the requested lifecycle stage."""
    updates: dict[str, Any] = {"status": next_stage}
    if approved is not None:
        updates["approved"] = bool(approved)
    return update_strategy_manifest(name, updates, path)


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
