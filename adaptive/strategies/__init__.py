from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AdaptiveSignal:
    """Canonical signal object passed between strategies and the engine."""
    strategy: str       # "smc_session" | "london_breakout" | "ny_momentum"
    pair: str           # "EURUSD" | "GBPUSD" | "USDJPY"
    direction: str      # "LONG" | "SHORT"
    entry_price: float
    sl_price: float
    tp_price: float
    session: str        # "london" | "new_york" | "asian"
    timestamp: str      # ISO-8601 UTC
    reason: str
    metadata: dict = field(default_factory=dict)
