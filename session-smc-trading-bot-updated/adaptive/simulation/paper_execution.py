"""
S4 — Paper Execution.

Simulates trade lifecycle without any broker interaction.
Tracks open trades, updates on new price data, and closes at SL/TP.

Public API:
    PaperExecution()
        .open_trade(signal)      -> str  (trade_id)
        .update(trade_id, price) -> dict | None  (closed trade if hit SL/TP)
        .get_open()              -> list[dict]
        .get_closed()            -> list[dict]
        .close_all(price)        -> list[dict]  (session-end close)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from adaptive.strategies import AdaptiveSignal


class PaperExecution:
    def __init__(self) -> None:
        self._open: dict[str, dict] = {}
        self._closed: list[dict] = []

    def open_trade(self, signal: AdaptiveSignal) -> str:
        """Register a new paper trade. Returns the trade_id."""
        trade_id = str(uuid.uuid4())[:8]
        self._open[trade_id] = {
            "trade_id":   trade_id,
            "strategy":   signal.strategy,
            "pair":       signal.pair,
            "direction":  signal.direction,
            "entry":      signal.entry_price,
            "sl":         signal.sl_price,
            "tp":         signal.tp_price,
            "session":    signal.session,
            "opened_at":  datetime.now(timezone.utc).isoformat(),
            "status":     "open",
            "pnl_r":      0.0,
        }
        return trade_id

    def update(self, trade_id: str, price: float) -> Optional[dict]:
        """
        Feed the current price. Returns the closed trade dict if SL or TP hit,
        otherwise returns None.
        """
        trade = self._open.get(trade_id)
        if trade is None:
            return None

        direction = trade["direction"]
        entry     = trade["entry"]
        sl        = trade["sl"]
        tp        = trade["tp"]
        risk      = abs(entry - sl)

        hit_tp = (direction == "LONG"  and price >= tp) or \
                 (direction == "SHORT" and price <= tp)
        hit_sl = (direction == "LONG"  and price <= sl) or \
                 (direction == "SHORT" and price >= sl)

        if hit_tp or hit_sl:
            exit_price = tp if hit_tp else sl
            pnl_r = ((exit_price - entry) / risk) if direction == "LONG" \
                    else ((entry - exit_price) / risk)
            trade.update({
                "status":    "tp" if hit_tp else "sl",
                "exit":      exit_price,
                "pnl_r":     round(pnl_r, 3),
                "closed_at": datetime.now(timezone.utc).isoformat(),
            })
            self._closed.append(trade)
            del self._open[trade_id]
            return trade

        # Update unrealised R
        unrealised = ((price - entry) / risk) if direction == "LONG" \
                     else ((entry - price) / risk)
        trade["pnl_r"] = round(unrealised, 3)
        return None

    def close_all(self, price: float, reason: str = "session_end") -> list[dict]:
        """Force-close all open trades at the given price."""
        closed = []
        for trade_id in list(self._open):
            trade  = self._open[trade_id]
            entry  = trade["entry"]
            sl     = trade["sl"]
            risk   = abs(entry - sl)
            pnl_r  = ((price - entry) / risk) if trade["direction"] == "LONG" \
                     else ((entry - price) / risk)
            trade.update({
                "status":    reason,
                "exit":      price,
                "pnl_r":     round(pnl_r, 3),
                "closed_at": datetime.now(timezone.utc).isoformat(),
            })
            self._closed.append(trade)
            closed.append(trade)
        self._open.clear()
        return closed

    def get_open(self) -> list[dict]:
        return list(self._open.values())

    def get_closed(self) -> list[dict]:
        return list(self._closed)
