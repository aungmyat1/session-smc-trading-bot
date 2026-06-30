"""smc_bot/broker/metaapi_executor.py"""

from __future__ import annotations

import logging
import os
from decimal import Decimal, ROUND_HALF_UP
import inspect

log = logging.getLogger(__name__)


def _round_volume(volume: float) -> float:
    return float(Decimal(str(volume)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


try:
    from metaapi_cloud_sdk import MetaApi
except ImportError:
    MetaApi = None


class MetaApiExecutor:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.token = os.getenv("METAAPI_TOKEN", cfg["metaapi"].get("token", ""))
        self.account_id = os.getenv(
            "METAAPI_ACCOUNT_ID", cfg["metaapi"].get("account_id", "")
        )
        self.timeout = cfg["metaapi"].get("deploy_timeout", 300)
        self._api = None
        self._account = None
        self._conn = None

    async def connect(self) -> None:
        if MetaApi is None:
            raise RuntimeError(
                "metaapi-cloud-sdk not installed. Run: pip install metaapi-cloud-sdk"
            )
        if not self.token or not self.account_id:
            raise RuntimeError(
                "METAAPI_TOKEN and METAAPI_ACCOUNT_ID must be set in .env"
            )

        log.info("Connecting to MetaAPI account %s …", self.account_id)
        self._api = MetaApi(self.token)
        self._account = await self._api.metatrader_account_api.get_account(
            self.account_id
        )

        state = self._account.state
        if state not in ("DEPLOYING", "DEPLOYED"):
            log.info("Deploying MT5 account (state=%s) …", state)
            await self._account.deploy()

        log.info("Waiting for MT5 connection (timeout=%ds) …", self.timeout)
        await self._account.wait_connected(timeout_in_seconds=self.timeout)

        conn = self._account.get_streaming_connection()
        if inspect.isawaitable(conn):
            conn = await conn
        self._conn = conn
        await self._conn.connect()
        await self._conn.wait_synchronized(timeout_in_seconds=self.timeout)
        log.info("MetaAPI connected and synchronised ✓")

    async def disconnect(self) -> None:
        if self._conn:
            await self._conn.close()
        if self._api:
            self._api.close()
        log.info("MetaAPI disconnected")

    def _check_connected(self) -> None:
        if self._conn is None:
            raise RuntimeError("MetaApiExecutor.connect() has not been called.")

    async def get_balance(self) -> float:
        self._check_connected()
        info = await self._conn.get_account_information()
        return float(info.get("equity", info.get("balance", 0.0)))

    async def get_today_closed_pnl(self) -> float:
        self._check_connected()
        from datetime import datetime, timezone

        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        history = await self._conn.get_deals_by_time_range(
            today_start,
            datetime.now(timezone.utc),
        )
        total_pnl = sum(
            float(d.get("profit", 0))
            for d in history
            if d.get("type") not in ("DEAL_TYPE_BALANCE", "DEAL_TYPE_CREDIT")
        )
        return total_pnl

    async def place_market_order(
        self,
        symbol: str,
        side: str,
        volume: float,
        sl: float,
        tp: float,
        comment: str = "",
    ) -> dict:
        self._check_connected()
        volume = _round_volume(volume)

        log.info(
            "MARKET %s %s %.2f lots | SL=%.5f TP=%.5f [%s]",
            side.upper(),
            symbol,
            volume,
            sl,
            tp,
            comment,
        )

        if side == "long":
            result = await self._conn.create_market_buy_order(
                symbol,
                volume,
                stop_loss=sl,
                take_profit=tp,
                options={"comment": comment},
            )
        else:
            result = await self._conn.create_market_sell_order(
                symbol,
                volume,
                stop_loss=sl,
                take_profit=tp,
                options={"comment": comment},
            )

        log.info("Order placed → positionId=%s", result.get("positionId"))
        return result

    async def place_limit_order(
        self,
        symbol: str,
        side: str,
        volume: float,
        price: float,
        sl: float,
        tp: float,
        comment: str = "",
    ) -> dict:
        self._check_connected()
        volume = _round_volume(volume)

        log.info(
            "LIMIT %s %s %.2f lots @ %.5f | SL=%.5f TP=%.5f [%s]",
            side.upper(),
            symbol,
            volume,
            price,
            sl,
            tp,
            comment,
        )

        if side == "long":
            result = await self._conn.create_limit_buy_order(
                symbol,
                volume,
                price,
                stop_loss=sl,
                take_profit=tp,
                options={"comment": comment},
            )
        else:
            result = await self._conn.create_limit_sell_order(
                symbol,
                volume,
                price,
                stop_loss=sl,
                take_profit=tp,
                options={"comment": comment},
            )

        log.info("Limit order placed → orderId=%s", result.get("orderId"))
        return result

    async def place_reduce_only(
        self,
        position_id: str,
        volume: float,
        comment: str = "partial_close",
    ) -> dict:
        self._check_connected()
        volume = _round_volume(volume)
        log.info(
            "PARTIAL CLOSE positionId=%s volume=%.2f [%s]",
            position_id,
            volume,
            comment,
        )
        result = await self._conn.close_position_partially(position_id, volume)
        return result

    async def set_sl(self, position_id: str, new_sl: float) -> dict:
        self._check_connected()
        log.info("SET SL positionId=%s new_sl=%.5f", position_id, new_sl)
        result = await self._conn.modify_position(position_id, stop_loss=new_sl)
        return result

    async def set_tp(self, position_id: str, new_tp: float) -> dict:
        self._check_connected()
        log.info("SET TP positionId=%s new_tp=%.5f", position_id, new_tp)
        result = await self._conn.modify_position(position_id, take_profit=new_tp)
        return result

    async def get_open_positions(self) -> list[dict]:
        self._check_connected()
        positions = await self._conn.get_positions()
        return positions or []

    async def get_positions_for_symbol(self, symbol: str) -> list[dict]:
        all_pos = await self.get_open_positions()
        return [p for p in all_pos if p.get("symbol") == symbol]

    async def close_position(self, position_id: str) -> dict:
        self._check_connected()
        log.info("CLOSE positionId=%s", position_id)
        result = await self._conn.close_position(position_id)
        return result

    async def get_current_price(self, symbol: str) -> dict:
        self._check_connected()
        price = await self._conn.get_symbol_price(symbol)
        return {
            "bid": float(price.get("bid", 0)),
            "ask": float(price.get("ask", 0)),
            "mid": (float(price.get("bid", 0)) + float(price.get("ask", 0))) / 2,
        }

    async def get_candles(
        self,
        symbol: str,
        timeframe: str,
        count: int = 500,
    ) -> list[dict]:
        self._check_connected()
        candles = await self._conn.get_historical_candles(symbol, timeframe, count)
        return candles or []
