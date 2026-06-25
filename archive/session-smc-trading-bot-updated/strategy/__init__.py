"""
Strategy layer — EMPTY PLACEHOLDER.

This module will house the SMC signal chain once Phase-0 backtest passes:
  Phase 1  Session Definition
  Phase 2  HTF Bias (4H + 1H)
  Phase 3  Session Range Build
  Phase 4  Session Classification
  Phase 5  Liquidity Sweep
  Phase 6  15M CHoCH
  Phase 7  15M BOS
  Phase 8  15M Displacement
  Phase 9  15M FVG Retest
  Phase 10 Risk Management
  Phase 11 Trade Management

Until Phase-0 gate is cleared (n≥50, net PF>1.0 at standard + 2× spread),
generate_signal() always returns None so the execution layer produces no trades.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class Signal:
    symbol: str
    direction: str          # 'long' | 'short'
    entry: float
    sl: float
    tp1: float
    tp2: float
    setup_type: str         # 'A' | 'B' | 'C'
    session: str


def generate_signal(
    symbol: str,
    candles: dict,          # {'4h': [...], '1h': [...], '15m': [...]}
    session: str,
) -> Optional[Signal]:
    """
    Entry point for the strategy layer.

    Returns a Signal if all 11 phases are satisfied, otherwise None.
    Currently always returns None — strategy not yet implemented.
    """
    # TODO (Phase-0 complete): implement SMC signal chain
    return None
