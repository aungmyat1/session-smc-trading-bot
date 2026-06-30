"""
ST-A2 Adapter — wraps strategy.session_liquidity output into core.Signal.

DO NOT modify the underlying strategy. This adapter is a thin translation layer
that maps ST-A2's own Signal dataclass to the canonical core.Signal.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from core.base_strategy import BaseStrategy
from core.signal import Signal


class ST_A2Adapter(BaseStrategy):
    """Adapter for Strategy A2: Session Liquidity + 15M SMC Confirmation."""

    @property
    def name(self) -> str:
        return "ST-A2"

    def generate_signal(self, data: dict) -> Optional[Signal]:
        """
        Args:
            data: {
                "symbol":  str,
                "m15":     list[dict],   # 200 M15 candles
                "h4":      list[dict],   # 100 H4 candles
                "config":  dict,         # optional, defaults to DEFAULT_CONFIG
            }

        Returns:
            Signal (most recent only) or None.
        """
        try:
            from strategy.session_liquidity.session_strategy import (
                run_strategy,
                DEFAULT_CONFIG,
            )
        except ImportError:
            return None

        m15 = data.get("m15", [])
        h4 = data.get("h4", [])
        symbol = data.get("symbol", "")
        config = data.get("config", DEFAULT_CONFIG)

        if len(m15) < 50:
            return None

        raw_signals = run_strategy(m15, h4, symbol, config)
        if not raw_signals:
            return None

        raw = raw_signals[-1]
        action = "BUY" if raw.side.lower() == "long" else "SELL"

        return Signal(
            timestamp=datetime.now(timezone.utc).isoformat(),
            strategy_name=self.name,
            symbol=symbol,
            action=action,
            order_type="MARKET",
            entry_price=float(raw.entry),
            stop_loss=float(raw.stop_loss),
            take_profit=float(raw.take_profit),
            risk_percent=0.30,  # validated tier-1: 0.30% per strategy_portfolio.yaml
            confidence=1.0,
            metadata={
                "session": raw.session,
                "risk_pips": float(getattr(raw, "risk_pips", 0)),
                "reward_pips": float(getattr(raw, "reward_pips", 0)),
                "rr": float(getattr(raw, "rr", 0)),
                "reason": getattr(raw, "reason", ""),
            },
        )
