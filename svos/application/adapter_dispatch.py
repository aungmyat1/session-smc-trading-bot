"""Strategy Adapter Dispatch — resolves a catalog strategy name to an executable adapter.

The SVOS platform is strategy-agnostic. This module is the single place that
maps catalog names and adapter type keys to concrete BaseStrategy subclasses.
No other module may hard-code adapter class names or import them directly.

Resolution order (first match wins):
  1. Exact match on catalog entry's "adapter_type" field.
  2. Exact match on the strategy catalog name.
  3. Case-insensitive prefix/substring match on the catalog name.

The registry is built lazily on first use. Adapters that fail to import
(missing optional dependencies, etc.) are recorded as UNAVAILABLE and do not
block the resolution of other adapters.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Any

from core.base_strategy import BaseStrategy


@dataclass(frozen=True)
class AdapterEntry:
    key: str
    adapter_class: type[BaseStrategy] | None
    error: str = ""

    @property
    def available(self) -> bool:
        return self.adapter_class is not None


class StrategyAdapterRegistry:
    """Resolves catalog strategy names to executable adapter classes."""

    # Canonical mapping from adapter_type keys → qualified class path.
    # This is the authoritative source; strategies/adapters/__init__.py
    # may be used as a convenience re-export but is not the authority here.
    _ADAPTER_MAP: dict[str, str] = {
        "AdaptiveSMC": "strategies.adapters.adaptive_smc_adapter.AdaptiveSMCAdapter",
        "LondonBreakout": "strategies.adapters.london_breakout_adapter.LondonBreakoutAdapter",
        "NYMomentum": "strategies.adapters.ny_momentum_adapter.NYMomentumAdapter",
        "SMCOrderBlockFVGSession": "strategies.adapters.smc_ob_fvg_session_adapter.SMCOrderBlockFVGSessionAdapter",
        "ST-A2": "strategies.adapters.st_a2_adapter.ST2Adapter",
        "ST-B1": "strategies.adapters.st_b1_adapter.STB1Adapter",
        "VWAPBreakout": "strategies.adapters.vwap_adapter.VWAPBreakoutAdapter",
        "VWAPMeanReversion": "strategies.adapters.vwap_adapter.VWAPMeanReversionAdapter",
    }

    # Aliases: catalog strategy name → adapter_type key
    _NAME_ALIASES: dict[str, str] = {
        "ST-A2": "ST-A2",
        "ST-B1": "ST-B1",
        "LondonBreakout": "LondonBreakout",
        "NYMomentum": "NYMomentum",
        "AdaptiveSMC": "AdaptiveSMC",
        "SMC-OB-FVG-Session": "SMCOrderBlockFVGSession",
        "SMCOrderBlockFVGSession": "SMCOrderBlockFVGSession",
        "VWAPBreakout": "VWAPBreakout",
        "VWAPMeanReversion": "VWAPMeanReversion",
    }

    def __init__(self) -> None:
        self._cache: dict[str, AdapterEntry] = {}

    def resolve(self, strategy: str, manifest: dict[str, Any] | None = None) -> AdapterEntry:
        """Resolve a strategy name to its adapter entry.

        Args:
            strategy: Catalog strategy name.
            manifest: Optional catalog manifest dict (may contain adapter_type).

        Returns:
            AdapterEntry — check .available before calling .adapter_class.
        """
        manifest = manifest or {}
        adapter_type_key = (
            str(manifest.get("adapter_type", "")).strip()
            or self._NAME_ALIASES.get(strategy, "")
            or strategy
        )

        if adapter_type_key in self._cache:
            return self._cache[adapter_type_key]

        entry = self._load(adapter_type_key)
        self._cache[adapter_type_key] = entry
        return entry

    def resolve_and_instantiate(
        self,
        strategy: str,
        manifest: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> BaseStrategy:
        """Resolve and instantiate the strategy adapter.

        Raises:
            KeyError: If the strategy cannot be resolved to a known adapter.
            ImportError: If the adapter module cannot be imported.
        """
        entry = self.resolve(strategy, manifest)
        if not entry.available:
            raise ImportError(
                f"Adapter for strategy {strategy!r} is unavailable: {entry.error}"
            )
        return entry.adapter_class(**kwargs)  # type: ignore[misc]

    def list_available(self) -> list[str]:
        """Return the list of resolvable adapter type keys."""
        return sorted(self._ADAPTER_MAP.keys())

    def health(self) -> dict[str, Any]:
        """Load all adapters and return availability status for each."""
        results: dict[str, Any] = {}
        for key in self._ADAPTER_MAP:
            entry = self._load(key)
            results[key] = {
                "available": entry.available,
                "error": entry.error,
                "class": entry.adapter_class.__name__ if entry.adapter_class else None,
            }
        return results

    def _load(self, key: str) -> AdapterEntry:
        qualified = self._ADAPTER_MAP.get(key)
        if qualified is None:
            return AdapterEntry(key=key, adapter_class=None, error=f"No adapter registered for key {key!r}")
        module_path, class_name = qualified.rsplit(".", 1)
        try:
            module = importlib.import_module(module_path)
            cls = getattr(module, class_name)
            if not (isinstance(cls, type) and issubclass(cls, BaseStrategy)):
                return AdapterEntry(key=key, adapter_class=None, error=f"{qualified} is not a BaseStrategy subclass")
            return AdapterEntry(key=key, adapter_class=cls)
        except Exception as exc:
            return AdapterEntry(key=key, adapter_class=None, error=str(exc))


# Module-level singleton — import and use directly.
_registry: StrategyAdapterRegistry | None = None


def get_adapter_registry() -> StrategyAdapterRegistry:
    global _registry
    if _registry is None:
        _registry = StrategyAdapterRegistry()
    return _registry


def resolve_adapter(
    strategy: str,
    manifest: dict[str, Any] | None = None,
) -> AdapterEntry:
    """Convenience wrapper around the module-level registry."""
    return get_adapter_registry().resolve(strategy, manifest)
