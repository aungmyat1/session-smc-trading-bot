"""
MetaAPI client — broker connectivity layer for VT Markets demo account.

LIVE_TRADING=false → DRY_RUN: connect, fetch data, log orders but never send them.
LIVE_TRADING=true  → real orders on connected account (owner sets this only).

All broker I/O (prices, positions, orders) goes through this class.
No strategy logic. No position sizing. Pure broker interface.
"""

import asyncio
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

LIVE_TRADING: bool = os.getenv("LIVE_TRADING", "false").lower() == "true"

# Maximum spread before rejecting a signal (market closed or news spike)
_MAX_SPREAD_PIPS: dict[str, float] = {"EURUSD": 3.0, "GBPUSD": 4.0}

# Hard ceiling on any single MetaAPI RPC call. Prevents indefinite await when
# the SDK is reconnecting and its internal request queue never flushes.
RPC_TIMEOUT_S: int = 30


# ── Data types ────────────────────────────────────────────────────────────────

@dataclass
class AccountInfo:
    balance: float
    equity: float
    margin: float
    free_margin: float
    leverage: int
    currency: str


@dataclass
class SymbolPrice:
    bid: float
    ask: float
    spread_pips: float
    time: str = ""


@dataclass
class BrokerPosition:
    position_id: str
    symbol: str
    direction: str   # 'long' | 'short'
    volume: float
    open_price: float
    sl: float
    tp: float
    profit: float
    magic: int


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


# ── Client ────────────────────────────────────────────────────────────────────

class MetaAPIClient:
    """
    Wraps MetaAPI RPC connection. All broker calls flow through here.

    Usage:
        client = MetaAPIClient(token, account_id)
        await client.connect()
        info = await client.get_account_info()
        ...
        await client.disconnect()
    """

    def __init__(self, token: str, account_id: str) -> None:
        self._token = token
        self._account_id = account_id
        self._api = None
        self._account = None
        self._connection = None
        self._connected: bool = False

    # ── RPC wrapper ───────────────────────────────────────────────────────────

    async def _rpc(self, coro):
        """Wrap an SDK RPC coroutine with RPC_TIMEOUT_S deadline.

        On timeout: logs ERROR, marks client disconnected, re-raises
        asyncio.TimeoutError so callers can distinguish it from SDK errors.
        """
        try:
            return await asyncio.wait_for(coro, timeout=RPC_TIMEOUT_S)
        except asyncio.TimeoutError:
            logger.error(
                "MetaAPI RPC timeout after %ds — marking disconnected", RPC_TIMEOUT_S
            )
            self._connected = False
            raise

    # ── Connection ────────────────────────────────────────────────────────────

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def connect(self) -> None:
        try:
            from metaapi_cloud_sdk import MetaApi
        except ImportError:
            raise RuntimeError(
                "metaapi-cloud-sdk not installed — run: pip install metaapi-cloud-sdk>=29"
            )

        self._api = MetaApi(self._token)
        self._account = await self._api.metatrader_account_api.get_account(self._account_id)

        if self._account.state not in ("DEPLOYING", "DEPLOYED"):
            logger.info("Deploying MetaAPI account…")
            await self._account.deploy()

        logger.info("Waiting for broker connection…")
        await self._account.wait_connected()

        self._connection = self._account.get_rpc_connection()
        await self._connection.connect()
        await self._connection.wait_synchronized(60)

        self._connected = True
        logger.info("MetaAPI connected (account=%s  live=%s)", self._account_id, LIVE_TRADING)

    async def disconnect(self) -> None:
        self._connected = False
        if self._connection:
            await self._connection.close()
        if self._api:
            self._api.close()
        logger.info("MetaAPI disconnected")

    async def reconnect(self) -> bool:
        """Re-synchronize the existing SDK connection after a drop.

        Returns True if synchronized within 70 seconds, False otherwise.
        Does not re-create the MetaApi or account objects — the SDK's own
        reconnect loop has already re-established the WebSocket by the time
        this is called; we just wait for synchronization to complete.
        """
        if self._connection is None:
            logger.error("reconnect() called but no connection object exists")
            return False
        logger.info("MetaAPI reconnect: waiting for synchronization…")
        try:
            await asyncio.wait_for(
                self._connection.wait_synchronized(60),
                timeout=70.0,
            )
            self._connected = True
            logger.info("MetaAPI reconnected successfully")
            return True
        except Exception as exc:
            logger.error("MetaAPI reconnect failed: %s", exc)
            self._connected = False
            return False

    def connection_status(self) -> dict:
        """Returns connection state dict for health-monitor heartbeats."""
        return {
            "connected": self._connected,
            "live_trading": LIVE_TRADING,
            "account_id": self._account_id,
        }

    # ── Market data ───────────────────────────────────────────────────────────

    async def get_account_info(self) -> AccountInfo:
        if not self._connected:
            raise RuntimeError("Not connected — call connect() first")
        raw = await self._rpc(self._connection.get_account_information())
        return AccountInfo(
            balance=raw.get("balance", 0.0),
            equity=raw.get("equity", 0.0),
            margin=raw.get("margin", 0.0),
            free_margin=raw.get("freeMargin", 0.0),
            leverage=raw.get("leverage", 0),
            currency=raw.get("currency", "USD"),
        )

    async def get_symbol_price(self, symbol: str) -> SymbolPrice:
        if not self._connected:
            raise RuntimeError("Not connected")
        raw = await self._rpc(self._connection.get_symbol_price(symbol))
        bid = float(raw.get("bid", 0.0))
        ask = float(raw.get("ask", 0.0))
        spread_pips = round((ask - bid) / 0.0001, 2)
        return SymbolPrice(bid=bid, ask=ask, spread_pips=spread_pips, time=raw.get("time", ""))

    async def check_spread(self, symbol: str) -> tuple[bool, float]:
        """
        Check whether the current spread is within acceptable range.

        Returns (spread_ok, spread_pips).
        Returns (False, 0.0) if not connected or price fetch fails.
        """
        if not self._connected:
            return False, 0.0
        try:
            price = await self.get_symbol_price(symbol)
            max_spread = _MAX_SPREAD_PIPS.get(symbol, 5.0)
            ok = price.spread_pips <= max_spread
            if not ok:
                logger.warning(
                    "Spread too wide for %s: %.1f > %.1f pip",
                    symbol, price.spread_pips, max_spread,
                )
            return ok, price.spread_pips
        except Exception as e:
            logger.warning("Spread check failed for %s: %s", symbol, e)
            return False, 0.0

    async def get_candles(
        self,
        symbol: str,
        timeframe: str,
        count: int = 300,
        end_time: "datetime | None" = None,
    ) -> list[dict]:
        """
        Fetch OHLCV bars from the broker.

        timeframe: '15m' | '4h' | '1h' | '1d'
        Returns list[dict] with keys: time, open, high, low, close, volume
        Returns [] if not connected.
        """
        if not self._connected:
            return []
        end_time = end_time or datetime.now(timezone.utc)
        try:
            raw = await self._rpc(self._connection.get_historical_candles(symbol, timeframe, end_time, count))
        except AttributeError:
            raw = await self._rpc(self._connection.get_candles(symbol, timeframe, end_time, count))
        return [
            {
                "time": c.get("time"),
                "open": c.get("open"),
                "high": c.get("high"),
                "low": c.get("low"),
                "close": c.get("close"),
                "volume": c.get("tickVolume", 0),
            }
            for c in (raw or [])
        ]

    async def get_open_positions(self, magic: "int | None" = None) -> list[BrokerPosition]:
        """
        Fetch open positions, optionally filtered by magic number.
        Returns [] if not connected.
        """
        if not self._connected:
            return []
        raw_list = await self._rpc(self._connection.get_positions())
        result: list[BrokerPosition] = []
        for p in (raw_list or []):
            if magic is not None and p.get("magic") != magic:
                continue
            result.append(BrokerPosition(
                position_id=p.get("id", ""),
                symbol=p.get("symbol", ""),
                direction="long" if p.get("type") == "POSITION_TYPE_BUY" else "short",
                volume=p.get("volume", 0.0),
                open_price=p.get("openPrice", 0.0),
                sl=p.get("stopLoss", 0.0),
                tp=p.get("takeProfit", 0.0),
                profit=p.get("profit", 0.0),
                magic=p.get("magic", 0),
            ))
        return result

    # ── Order execution ───────────────────────────────────────────────────────

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
        """
        Place a market order.

        When LIVE_TRADING=false: logs and returns a DRY_RUN OrderResult.
        When LIVE_TRADING=true: sends the order to the broker.
        """
        if not LIVE_TRADING:
            logger.info(
                "[DRY RUN] Would place %s %s vol=%.2f sl=%.5f tp=%.5f",
                direction.upper(), symbol, volume, sl, tp,
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

        if not self._connected:
            raise RuntimeError("Not connected — cannot place order")

        opts = {"magic": magic, "comment": comment}
        if direction == "long":
            result = await self._rpc(self._connection.create_market_buy_order(symbol, volume, sl, tp, opts))
        else:
            result = await self._rpc(self._connection.create_market_sell_order(symbol, volume, sl, tp, opts))

        order_id = str(result.get("orderId", result.get("id", "unknown")))
        entry = float(result.get("openPrice", 0.0))
        logger.info(
            "Order placed: %s %s id=%s entry=%.5f",
            direction.upper(), symbol, order_id, entry,
        )
        return OrderResult(
            order_id=order_id,
            symbol=symbol,
            direction=direction,
            volume=volume,
            entry_price=entry,
            sl=sl,
            tp=tp,
        )

    async def close_position(self, position_id: str) -> bool:
        """
        Close a position by ID.

        When LIVE_TRADING=false: logs and returns True (simulated close).
        Returns False if not connected in live mode.
        """
        if not LIVE_TRADING:
            logger.info("[DRY RUN] Would close position %s", position_id)
            return True
        if not self._connected:
            return False
        await self._rpc(self._connection.close_position(position_id))
        logger.info("Position closed: %s", position_id)
        return True
