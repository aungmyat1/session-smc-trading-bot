"""
Vantage Demo Executor — market data + order execution for Vantage MT5 demo.

DEMO_ONLY=true (env default): write operations are logged but NOT sent.
Set DEMO_ONLY=false only after safety checklist passes.

Public API:
    VantageDemoExecutor(connector)
        async .get_candles(symbol, timeframe, count) -> list[dict]
        async .get_price(symbol) -> dict
        async .get_account_info() -> dict
        async .get_positions() -> list[dict]
        async .place_order(symbol, direction, lots, sl, tp) -> dict
        async .close_position(position_id) -> bool
        async .modify_position(position_id, sl, tp) -> bool
"""

from __future__ import annotations

import logging
import os
import uuid

from execution.market_data import MarketDataProvider, MetaApiMarketDataProvider
from execution.mt5_connector import MT5Connector

_log = logging.getLogger("strategy_demo.vantage_executor")

_DEMO_ONLY = os.environ.get("DEMO_ONLY", "true").lower() not in ("false", "0", "no")

_PIP: dict[str, float] = {
    "EURUSD": 0.0001,
    "GBPUSD": 0.0001,
    "USDJPY": 0.01,
    "XAUUSD": 0.1,    # Gold: 1 pip = $0.10 (price quoted to 2 decimals, e.g. 2340.50)
}

_TF_MAP = {
    "M5": "5m", "M15": "15m", "H1": "1h", "H4": "4h",
    "m5": "5m", "m15": "15m", "h1": "1h", "h4": "4h",
}


class VantageDemoExecutor:
    def __init__(
        self,
        connector: MT5Connector,
        market_data_provider: MarketDataProvider | None = None,
    ) -> None:
        self._conn = connector
        self.demo_only = _DEMO_ONLY
        self._market_data = market_data_provider or MetaApiMarketDataProvider(
            account_getter=lambda: self._conn._account,
            connection_getter=lambda: self._conn.connection,
            reconnect_callback=self._conn.reconnect,
        )

    def _rpc(self):
        return self._conn.connection

    # ── Market data (always allowed) ───────────────────────────────────────

    async def get_candles(
        self, symbol: str, timeframe: str, count: int = 200
    ) -> list[dict]:
        tf = _TF_MAP.get(timeframe, timeframe)
        return await self._market_data.get_candles(symbol, tf, count)

    async def get_price(self, symbol: str) -> dict:
        p = await self._rpc().get_symbol_price(symbol)
        bid = float(p.get("bid", 0))
        ask = float(p.get("ask", 0))
        pip = _PIP.get(symbol, 0.0001)
        return {
            "bid":         bid,
            "ask":         ask,
            "spread_pips": round((ask - bid) / pip, 1),
            "time":        p.get("time", ""),
        }

    async def get_account_info(self) -> dict:
        info = await self._rpc().get_account_information()
        return {
            "balance":    float(info.get("balance", 0)),
            "equity":     float(info.get("equity", 0)),
            "margin":     float(info.get("margin", 0)),
            "free_margin":float(info.get("freeMargin", 0)),
            "currency":   info.get("currency", "USD"),
        }

    async def get_positions(self) -> list[dict]:
        positions = await self._rpc().get_positions()
        return [
            {
                "id":         p.get("id"),
                "symbol":     p.get("symbol"),
                "direction":  p.get("type", "").replace("POSITION_TYPE_", "").lower(),
                "lots":       p.get("volume"),
                "entry":      p.get("openPrice"),
                "sl":         p.get("stopLoss"),
                "tp":         p.get("takeProfit"),
                "profit":     p.get("profit"),
                "magic":      p.get("magic"),
            }
            for p in (positions or [])
        ]

    # ── Write operations (gated by DEMO_ONLY) ─────────────────────────────

    def _guard(self, action: str) -> bool:
        if self.demo_only:
            _log.info("DEMO_ONLY — would execute: %s", action)
            return False
        return True

    async def place_order(
        self,
        symbol: str,
        direction: str,        # "buy" | "sell"
        lots: float,
        sl: float,
        tp: float,
        magic: int = 21001,
        comment: str = "strategy-demo",
    ) -> dict:
        order_id = f"SIM-{symbol[:3]}-{uuid.uuid4().hex[:6].upper()}"
        if not self._guard(f"place_order {direction} {symbol} {lots}lot"):
            return {"order_id": order_id, "simulated": True, "symbol": symbol,
                    "direction": direction, "lots": lots, "sl": sl, "tp": tp}
        result = await self._rpc().create_market_buy_order(
            symbol, lots, sl, tp, {"magic": magic, "comment": comment}
        ) if direction == "buy" else await self._rpc().create_market_sell_order(
            symbol, lots, sl, tp, {"magic": magic, "comment": comment}
        )
        return {"order_id": result.get("orderId", order_id), "simulated": False,
                "symbol": symbol, "direction": direction, "lots": lots, "sl": sl, "tp": tp}

    async def close_position(self, position_id: str) -> bool:
        if not self._guard(f"close_position {position_id}"):
            return True   # simulated success
        try:
            await self._rpc().close_position(position_id)
            return True
        except Exception as exc:
            _log.error("close_position failed: %s", exc)
            return False

    async def modify_position(self, position_id: str, sl: float, tp: float) -> bool:
        if not self._guard(f"modify_position {position_id} SL={sl} TP={tp}"):
            return True
        try:
            await self._rpc().modify_position(position_id, sl, tp)
            return True
        except Exception as exc:
            _log.error("modify_position failed: %s", exc)
            return False
