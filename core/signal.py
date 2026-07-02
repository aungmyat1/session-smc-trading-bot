"""
Canonical Signal dataclass — the single contract between strategy and execution layers.

All strategies produce Signal. Execution layer consumes Signal. Neither layer
knows the internals of the other.

Compatibility properties (pair, side, entry) ensure existing execution code
(trade_journal, trade_manager) works without modification.
"""

from shared.strategy_api.signal import Signal

__all__ = ["Signal"]
