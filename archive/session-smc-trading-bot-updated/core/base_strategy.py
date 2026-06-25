"""
BaseStrategy — abstract interface all strategy adapters must implement.

The execution layer only ever calls generate_signal(data).
Strategy internals (indicators, SMC logic, ML models) are invisible to execution.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from core.signal import Signal


class BaseStrategy(ABC):
    """All strategy adapters inherit from this class."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique strategy identifier used in Signal.strategy_name and registry."""

    @abstractmethod
    def generate_signal(self, data: dict) -> Optional[Signal]:
        """
        Evaluate market data and return a Signal, or None if no trade.

        Args:
            data: strategy-specific dict — keys defined by each adapter.
                  Common keys: symbol, m15, h4, spread_pips, balance.

        Returns:
            Signal if a trade setup is confirmed, else None.
        """
