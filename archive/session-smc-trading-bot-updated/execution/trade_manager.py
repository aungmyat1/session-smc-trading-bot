"""
Trade Manager — open/close/modify/emergency for ST-A2 demo.

Isolated from existing execution/order_manager.py.
All write operations require DEMO_ONLY=false AND explicit call.

Public API:
    TradeManager(executor)
        async .open_position(signal, lots) -> dict
        async .close_position(position_id) -> bool
        async .modify_sl_tp(position_id, sl, tp) -> bool
        async .get_positions() -> list[dict]
        async .emergency_close_all() -> int  (count closed)
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

from execution.vantage_demo_executor import VantageDemoExecutor

_log = logging.getLogger("st_a2.trade_manager")

_MAGIC = 21099   # ST-A2 demo magic number


class TradeManager:
    def __init__(self, executor: VantageDemoExecutor) -> None:
        self._ex = executor

    async def open_position(self, signal, lots: float) -> dict:
        """
        Open a position from an ST-A2 signal dict or Signal dataclass.

        signal must have: symbol/pair, side/direction, entry, stop_loss/sl, take_profit/tp
        Returns order result dict.
        """
        symbol    = getattr(signal, "pair", None) or signal.get("symbol", "")
        direction = getattr(signal, "side", None) or signal.get("direction", "")
        sl        = getattr(signal, "stop_loss", None) or signal.get("stop_loss", 0.0)
        tp        = getattr(signal, "take_profit", None) or signal.get("take_profit", 0.0)

        # Normalise direction
        direction = direction.lower()
        if direction in ("long",):
            direction = "buy"
        elif direction in ("short",):
            direction = "sell"

        _log.info("Opening %s %s %.4f lots SL=%.5f TP=%.5f", direction, symbol, lots, sl, tp)
        result = await self._ex.place_order(
            symbol    = symbol,
            direction = direction,
            lots      = lots,
            sl        = sl,
            tp        = tp,
            magic     = _MAGIC,
            comment   = "ST-A2-demo",
        )
        result["opened_at"] = datetime.now(timezone.utc).isoformat()
        return result

    async def close_position(self, position_id: str) -> bool:
        _log.info("Closing position %s", position_id)
        return await self._ex.close_position(position_id)

    async def modify_sl_tp(self, position_id: str, sl: float, tp: float) -> bool:
        _log.info("Modifying %s SL=%.5f TP=%.5f", position_id, sl, tp)
        return await self._ex.modify_position(position_id, sl, tp)

    async def get_positions(self) -> list[dict]:
        positions = await self._ex.get_positions()
        return [p for p in positions if p.get("magic") == _MAGIC]

    async def emergency_close_all(self) -> int:
        """Force-close all ST-A2 positions. Returns count closed."""
        positions = await self.get_positions()
        count = 0
        for p in positions:
            pid = p.get("id", "")
            if pid:
                ok = await self.close_position(pid)
                if ok:
                    count += 1
                    _log.warning("EMERGENCY CLOSE: %s %s", p.get("symbol"), pid)
        _log.warning("Emergency close: %d positions closed.", count)
        return count
