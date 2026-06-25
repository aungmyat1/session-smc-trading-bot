"""
NY Momentum Adapter — wraps adaptive.strategies.ny_momentum_strategy
into core.Signal. DO NOT modify the underlying strategy.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from core.base_strategy import BaseStrategy
from core.signal import Signal


class NYMomentumAdapter(BaseStrategy):

    @property
    def name(self) -> str:
        return "NYMomentum"

    def generate_signal(self, data: dict) -> Optional[Signal]:
        """
        Args:
            data: {"symbol": str, "m15": list[dict]}
        """
        try:
            from adaptive.strategies.ny_momentum_strategy import generate_signals
        except ImportError:
            return None

        m15    = data.get("m15", [])
        symbol = data.get("symbol", "")

        if len(m15) < 30:
            return None

        raw_list = generate_signals(m15, symbol)
        if not raw_list:
            return None

        raw = raw_list[-1]
        action = "BUY" if raw.direction == "LONG" else "SELL"

        sl_pips = abs(raw.entry_price - raw.sl_price) / 0.0001
        tp_pips = abs(raw.tp_price - raw.entry_price) / 0.0001
        rr      = round(tp_pips / sl_pips, 2) if sl_pips else 0.0

        return Signal(
            timestamp=datetime.now(timezone.utc).isoformat(),
            strategy_name=self.name,
            symbol=symbol,
            action=action,
            order_type="MARKET",
            entry_price=float(raw.entry_price),
            stop_loss=float(raw.sl_price),
            take_profit=float(raw.tp_price),
            risk_percent=0.20,          # conditionally validated tier-2: 0.20% per strategy_portfolio.yaml
            confidence=min(1.0, rr / 2.5),   # 2R → 0.8, 2.5R+ → 1.0
            metadata={
                "session":     raw.session,
                "reason":      raw.reason,
                "risk_pips":   round(sl_pips, 1),
                "reward_pips": round(tp_pips, 1),
                "rr":          rr,
            },
        )
