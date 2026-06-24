"""
Adaptive SMC Adapter — wraps adaptive.strategies.smc_session_strategy
into core.Signal. DO NOT modify the underlying strategy.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from core.base_strategy import BaseStrategy
from core.signal import Signal


class AdaptiveSMCAdapter(BaseStrategy):

    @property
    def name(self) -> str:
        return "AdaptiveSMC"

    def generate_signal(self, data: dict) -> Optional[Signal]:
        """
        Args:
            data: {"symbol": str, "m15": list[dict], "h4": list[dict],
                   "spread_pips": float, "htf_bias": str}
        """
        try:
            from adaptive.strategies.smc_session_strategy import SMCSessionStrategy
        except ImportError:
            return None

        m15    = data.get("m15", [])
        h4     = data.get("h4", [])
        symbol = data.get("symbol", "")

        if len(m15) < 50:
            return None

        strategy  = SMCSessionStrategy()
        raw_list  = strategy.generate_signals(m15, h4, symbol)

        if not raw_list:
            return None

        raw    = raw_list[-1]
        action = "BUY" if raw.direction == "LONG" else "SELL"

        sl_pips = abs(raw.entry_price - raw.sl_price) / 0.0001
        tp_pips = abs(raw.tp_price - raw.entry_price) / 0.0001
        rr      = round(tp_pips / sl_pips, 2) if sl_pips else 0.0

        # Adaptive SMC requires both liquidity swept + structure confirmed
        liquidity_swept    = raw.metadata.get("liquidity_swept", False)
        structure_confirmed = raw.metadata.get("structure_confirmed", False)
        confidence = 0.6
        if liquidity_swept:
            confidence += 0.2
        if structure_confirmed:
            confidence += 0.2

        return Signal(
            timestamp=datetime.now(timezone.utc).isoformat(),
            strategy_name=self.name,
            symbol=symbol,
            action=action,
            order_type="MARKET",
            entry_price=float(raw.entry_price),
            stop_loss=float(raw.sl_price),
            take_profit=float(raw.tp_price),
            risk_percent=0.25,
            confidence=round(confidence, 2),
            metadata={
                "session":              raw.session,
                "reason":               raw.reason,
                "risk_pips":            round(sl_pips, 1),
                "reward_pips":          round(tp_pips, 1),
                "rr":                   rr,
                "liquidity_swept":      liquidity_swept,
                "structure_confirmed":  structure_confirmed,
            },
        )
