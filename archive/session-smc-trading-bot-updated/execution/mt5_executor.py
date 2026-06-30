"""
MT5 executor — MetaAPI Cloud SDK bridge to VT Markets.

LIVE_TRADING=false  → connect for data only; order calls are logged, not sent.
LIVE_TRADING=true   → orders execute on the connected account (demo or live).
"""

import asyncio
import logging
import os
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

LIVE_TRADING = os.getenv("LIVE_TRADING", "false").lower() == "true"


@dataclass
class OrderResult:
    order_id: str
    symbol: str
    direction: str
    volume: float
    entry_price: float
    sl: float
    tp: float
    dry_run: bool = False


@dataclass
class Position:
    position_id: str
    symbol: str
    direction: str
    volume: float
    open_price: float
    sl: float
    tp: float
    profit: float
    magic: int


class MT5Executor:
    """Wraps MetaAPI RPC connection for order management."""

    def __init__(self, token: str, account_id: str):
        self._token = token
        self._account_id = account_id
        self._api = None
        self._account = None
        self._connection = None

    async def connect(self) -> None:
        try:
            from metaapi_cloud_sdk import MetaApi
        except ImportError:
            raise RuntimeError(
                "metaapi-cloud-sdk not installed — run: pip install metaapi-cloud-sdk>=29"
            )

        self._api = MetaApi(self._token)
        self._account = await self._api.metatrader_account_api.get_account(
            self._account_id
        )

        if self._account.state not in ("DEPLOYING", "DEPLOYED"):
            logger.info("Deploying MetaAPI account…")
            await self._account.deploy()

        logger.info("Waiting for broker connection…")
        await self._account.wait_connected()

        self._connection = self._account.get_rpc_connection()
        await self._connection.connect()
        await self._connection.wait_synchronized({"timeoutInSeconds": 60})
        logger.info("MT5 connected via MetaAPI (account=%s)", self._account_id)

    async def disconnect(self) -> None:
        if self._connection:
            await self._connection.close()
        if self._api:
            self._api.close()
        logger.info("MT5 disconnected")

    async def get_account_info(self) -> dict:
        info = await self._connection.get_account_information()
        return {
            "balance": info.get("balance", 0.0),
            "equity": info.get("equity", 0.0),
            "margin": info.get("margin", 0.0),
            "free_margin": info.get("freeMargin", 0.0),
            "leverage": info.get("leverage", 0),
            "currency": info.get("currency", "USD"),
        }

    async def get_symbol_price(self, symbol: str) -> dict:
        price = await self._connection.get_symbol_price(symbol)
        return {
            "bid": price.get("bid"),
            "ask": price.get("ask"),
            "time": price.get("time"),
        }

    async def get_open_positions(self, magic: Optional[int] = None) -> list[Position]:
        raw = await self._connection.get_positions()
        positions = []
        for p in raw:
            if magic is not None and p.get("magic") != magic:
                continue
            positions.append(
                Position(
                    position_id=p.get("id", ""),
                    symbol=p.get("symbol", ""),
                    direction=(
                        "long" if p.get("type") == "POSITION_TYPE_BUY" else "short"
                    ),
                    volume=p.get("volume", 0.0),
                    open_price=p.get("openPrice", 0.0),
                    sl=p.get("stopLoss", 0.0),
                    tp=p.get("takeProfit", 0.0),
                    profit=p.get("profit", 0.0),
                    magic=p.get("magic", 0),
                )
            )
        return positions

    async def place_order(
        self,
        symbol: str,
        direction: str,
        volume: float,
        sl: float,
        tp: float,
        magic: int,
        comment: str = "",
    ) -> OrderResult:
        if not LIVE_TRADING:
            logger.info(
                "[DRY RUN] Would place %s %s: vol=%.2f sl=%.5f tp=%.5f",
                direction.upper(),
                symbol,
                volume,
                sl,
                tp,
            )
            return OrderResult(
                order_id="DRY_RUN",
                symbol=symbol,
                direction=direction,
                volume=volume,
                entry_price=0.0,
                sl=sl,
                tp=tp,
                dry_run=True,
            )

        opts = {"magic": magic, "comment": comment}
        if direction == "long":
            result = await self._connection.create_market_buy_order(
                symbol, volume, sl, tp, opts
            )
        else:
            result = await self._connection.create_market_sell_order(
                symbol, volume, sl, tp, opts
            )

        order_id = result.get("orderId", result.get("id", "unknown"))
        entry = result.get("openPrice", 0.0)
        logger.info(
            "Order placed: %s %s id=%s entry=%.5f",
            direction.upper(),
            symbol,
            order_id,
            entry,
        )

        return OrderResult(
            order_id=str(order_id),
            symbol=symbol,
            direction=direction,
            volume=volume,
            entry_price=entry,
            sl=sl,
            tp=tp,
        )

    async def close_position(self, position_id: str) -> bool:
        if not LIVE_TRADING:
            logger.info("[DRY RUN] Would close position %s", position_id)
            return True
        await self._connection.close_position(position_id)
        logger.info("Position closed: %s", position_id)
        return True

    async def modify_position(self, position_id: str, sl: float, tp: float) -> bool:
        if not LIVE_TRADING:
            logger.info(
                "[DRY RUN] Would modify position %s → sl=%.5f tp=%.5f",
                position_id,
                sl,
                tp,
            )
            return True
        await self._connection.modify_position(position_id, sl, tp)
        logger.info("Position modified: %s sl=%.5f tp=%.5f", position_id, sl, tp)
        return True

    async def get_trade_history(self, from_dt, to_dt) -> list[dict]:
        deals = await self._connection.get_deals_by_time_range(from_dt, to_dt)
        return deals or []
