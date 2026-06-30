"""
Canonical Signal dataclass — the single contract between strategy and execution layers.

All strategies produce Signal. Execution layer consumes Signal. Neither layer
knows the internals of the other.

Compatibility properties (pair, side, entry) ensure existing execution code
(trade_journal, trade_manager) works without modification.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class Signal:
    timestamp: str
    strategy_name: str
    symbol: str
    action: Literal["BUY", "SELL", "CLOSE"]
    order_type: Literal["MARKET", "LIMIT"] = "MARKET"
    entry_price: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    risk_percent: float = 0.25  # % of account, e.g. 0.25 = 0.25%
    confidence: float = 1.0  # 0.0–1.0
    ttl_seconds: int = 300  # signal expires after this many seconds
    metadata: dict = field(default_factory=dict)

    # ── Compatibility properties for existing execution/journal code ───────────

    @property
    def direction(self) -> str:
        """Canonical direction: 'BUY' | 'SELL' | 'CLOSE'  (same as action)."""
        return self.action

    @property
    def pair(self) -> str:
        return self.symbol

    @property
    def side(self) -> str:
        return "long" if self.action == "BUY" else "short"

    @property
    def entry(self) -> float:
        return self.entry_price

    @property
    def session(self) -> str:
        return self.metadata.get("session", "")

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "strategy_name": self.strategy_name,
            "symbol": self.symbol,
            "action": self.action,
            "order_type": self.order_type,
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "risk_percent": self.risk_percent,
            "confidence": self.confidence,
            "ttl_seconds": self.ttl_seconds,
            "metadata": self.metadata,
        }
