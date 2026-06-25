"""
Strategy Registry — central lookup for all registered strategies.

Execution layer calls get_strategy(name) to retrieve an adapter instance
without importing any strategy-specific code directly.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Type

from core.base_strategy import BaseStrategy

_registry: Dict[str, BaseStrategy] = {}


def register_strategy(strategy: BaseStrategy) -> None:
    """Register a strategy instance under its name."""
    _registry[strategy.name] = strategy


def get_strategy(name: str) -> Optional[BaseStrategy]:
    """Return registered strategy by name, or None if not found."""
    return _registry.get(name)


def list_strategies() -> List[str]:
    """Return sorted list of all registered strategy names."""
    return sorted(_registry.keys())


def clear_registry() -> None:
    """Clear all registrations — for testing only."""
    _registry.clear()
