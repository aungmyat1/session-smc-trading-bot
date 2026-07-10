"""
MT5Linux Connector — mt5linux/RPyC bridge connection for Vantage demo OR live
account, replacing the MetaAPI Cloud SDK path (ADR-0011).

Requires a Wine-hosted MT5 terminal logged into the target account, with the
mt5linux RPyC server running against it:
    python -m mt5linux <path-to-wine-python.exe>
See docs/svos/ADR-0011-MT5LINUX-BROKER-BRIDGE.md for the full rollout plan.

Env vars:
    MT5LINUX_HOST              — RPyC server host (default: localhost)
    MT5LINUX_PORT              — RPyC server port (default: 18812)
    VANTAGE_MT5_DEMO_LOGIN / _PASSWORD / _SERVER   — Vantage demo account
    VANTAGE-LIVE / VANTAGE-LIVE-PASSWORD / VANTAGE-SERVER  — Vantage live account
    DEMO_ONLY                  — true (default) = no write orders sent

Public API mirrors execution.mt5_connector.MT5Connector exactly:
    MT5LinuxConnector(mode="demo")  mode: "demo" | "live"
        async .connect()
        async .disconnect()
        async .reconnect()
        async .ensure_connected() -> bool
        async .heartbeat() -> dict
        .connection          — adapter exposing the same async RPC surface
                                (get_symbol_price, get_account_information,
                                get_positions, get_deals_by_position,
                                create_market_buy_order/create_market_sell_order,
                                close_position, modify_position) as the MetaAPI
                                connection object, so execution/vantage_demo_executor.py
                                needs no changes.
        .is_connected         -> bool
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_log = logging.getLogger("strategy_demo.mt5linux_connector")

_HB_TIMEOUT_S = 10
_RECONNECT_DELAY_S = 5
_LATENCY_PATH = Path("logs") / "latency_timeseries.jsonl"
_LATENCY_RETENTION = 1000

_CREDENTIAL_VARS = {
    "demo": {
        "login": "VANTAGE_MT5_DEMO_LOGIN",
        "password": "VANTAGE_MT5_DEMO_PASSWORD",
        "server": "VANTAGE_MT5_DEMO_SERVER",
    },
    "live": {
        "login": "VANTAGE-LIVE",
        "password": "VANTAGE-LIVE-PASSWORD",
        "server": "VANTAGE-SERVER",
    },
}

# MT5 position/deal integer codes -> MetaAPI-shaped string constants, so the
# adapter's return dicts match what execution/vantage_demo_executor.py already
# expects from the MetaAPI RPC connection.
_POSITION_TYPE = {0: "POSITION_TYPE_BUY", 1: "POSITION_TYPE_SELL"}
_DEAL_ENTRY_OUT_CODES = {1, 3}  # DEAL_ENTRY_OUT, DEAL_ENTRY_OUT_BY


class MT5LinuxConnector:
    def __init__(self, mode: str = "demo") -> None:
        self._mode = mode
        creds = _CREDENTIAL_VARS.get(mode, _CREDENTIAL_VARS["demo"])
        self._login = os.environ.get(creds["login"], "")
        self._password = os.environ.get(creds["password"], "")
        self._server = os.environ.get(creds["server"], "")
        self._host = os.environ.get("MT5LINUX_HOST", "localhost")
        self._port = int(os.environ.get("MT5LINUX_PORT", "18812"))
        self._mt5 = None
        self._connection: _MT5RPCAdapter | None = None
        self._last_hb: datetime | None = None
        self._reconnecting = False
        self._reconnect_count = 0
        self._last_reconnect_at = ""

    # ── Connection ─────────────────────────────────────────────────────────

    async def connect(self) -> None:
        if not self._login or not self._password or not self._server:
            creds = _CREDENTIAL_VARS.get(self._mode, _CREDENTIAL_VARS["demo"])
            raise RuntimeError(
                f"{creds['login']}/{creds['password']}/{creds['server']} not set in .env"
            )
        try:
            from mt5linux import MetaTrader5
        except ImportError:
            raise RuntimeError("pip install mt5linux")

        _log.info("Connecting to Vantage %s via mt5linux (%s:%s)…", self._mode, self._host, self._port)
        mt5 = MetaTrader5(host=self._host, port=self._port)

        def _init_and_login() -> None:
            if not mt5.initialize():
                raise RuntimeError(f"mt5linux initialize() failed: {mt5.last_error()}")
            if not mt5.login(int(self._login), password=self._password, server=self._server):
                raise RuntimeError(f"mt5linux login() failed: {mt5.last_error()}")

        await asyncio.to_thread(_init_and_login)
        self._mt5 = mt5
        self._connection = _MT5RPCAdapter(mt5)
        self._last_hb = datetime.now(timezone.utc)
        _log.info("Connected to Vantage MT5 %s via mt5linux.", self._mode)

    async def disconnect(self) -> None:
        if self._mt5:
            try:
                await asyncio.to_thread(self._mt5.shutdown)
            except Exception:
                pass
        self._mt5 = None
        self._connection = None
        _log.info("Disconnected.")

    async def reconnect(self) -> None:
        if self._reconnecting:
            _log.debug("Reconnect already in progress — skipping duplicate call")
            return
        self._reconnecting = True
        try:
            self._reconnect_count += 1
            self._last_reconnect_at = datetime.now(timezone.utc).isoformat()
            _log.warning("Reconnecting to mt5linux…")
            await self.disconnect()
            await asyncio.sleep(_RECONNECT_DELAY_S)
            await self.connect()
        finally:
            self._reconnecting = False

    async def ensure_connected(self) -> bool:
        if self._connection is None:
            await self.reconnect()
            return False
        try:
            await asyncio.wait_for(
                self._connection.get_account_information(),
                timeout=_HB_TIMEOUT_S,
            )
            return True
        except Exception as exc:
            _log.warning("Connection liveness check failed (%s) — reconnecting", exc)
            await self.reconnect()
            return False

    # ── Heartbeat ──────────────────────────────────────────────────────────

    async def heartbeat(self) -> dict:
        import time
        t0 = time.monotonic()
        try:
            await self._connection.get_account_information()
            latency = round((time.monotonic() - t0) * 1000)
            self._last_hb = datetime.now(timezone.utc)
            payload = {
                "connected": True,
                "latency_ms": latency,
                "last_heartbeat": self._last_hb.isoformat(),
            }
            self._append_latency_sample(payload)
            return payload
        except Exception as exc:
            _log.warning("Heartbeat failed: %s — reconnecting", exc)
            try:
                await self.reconnect()
                payload = {"connected": True, "latency_ms": -1,
                           "last_heartbeat": self._last_hb.isoformat() if self._last_hb else ""}
                self._append_latency_sample(payload)
                return payload
            except Exception:
                payload = {"connected": False, "latency_ms": -1, "last_heartbeat": ""}
                self._append_latency_sample(payload)
                return payload

    @property
    def is_connected(self) -> bool:
        return self._connection is not None

    @property
    def connection(self):
        return self._connection

    @property
    def reconnect_attempts_total(self) -> int:
        return self._reconnect_count

    @property
    def last_reconnect_at(self) -> str:
        return self._last_reconnect_at

    def _append_latency_sample(self, payload: dict) -> None:
        _LATENCY_PATH.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "latency_ms": payload.get("latency_ms", -1),
            "connected": bool(payload.get("connected", False)),
        }
        lines: list[str] = []
        if _LATENCY_PATH.exists():
            try:
                lines = _LATENCY_PATH.read_text(encoding="utf-8").splitlines()
            except OSError:
                lines = []
        lines.append(json.dumps(entry, sort_keys=True))
        if len(lines) > _LATENCY_RETENTION:
            lines = lines[-_LATENCY_RETENTION:]
        _LATENCY_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


class _MT5RPCAdapter:
    """
    Wraps the synchronous mt5linux client and exposes the same async method
    names/return shapes as the MetaAPI RPC connection object, so
    execution/vantage_demo_executor.py works against either backend unchanged.
    """

    def __init__(self, mt5: Any) -> None:
        self._mt5 = mt5

    async def get_symbol_price(self, symbol: str) -> dict:
        tick = await asyncio.to_thread(self._mt5.symbol_info_tick, symbol)
        if tick is None:
            raise RuntimeError(f"symbol_info_tick({symbol}) returned None: {self._mt5.last_error()}")
        return {
            "bid": tick.bid,
            "ask": tick.ask,
            "time": datetime.fromtimestamp(tick.time, tz=timezone.utc).isoformat(),
        }

    async def get_account_information(self) -> dict:
        info = await asyncio.to_thread(self._mt5.account_info)
        if info is None:
            raise RuntimeError(f"account_info() returned None: {self._mt5.last_error()}")
        return {
            "balance": float(info.balance),
            "equity": float(info.equity),
            "margin": float(info.margin),
            "freeMargin": float(info.margin_free),
            "currency": info.currency,
        }

    async def get_positions(self) -> list[dict]:
        positions = await asyncio.to_thread(self._mt5.positions_get)
        return [
            {
                "id": str(p.ticket),
                "symbol": p.symbol,
                "type": _POSITION_TYPE.get(p.type, "POSITION_TYPE_BUY"),
                "volume": p.volume,
                "openPrice": p.price_open,
                "currentPrice": p.price_current,
                "stopLoss": p.sl,
                "takeProfit": p.tp,
                "profit": p.profit,
                "magic": p.magic,
            }
            for p in (positions or [])
        ]

    async def get_deals_by_position(self, position_id: str) -> dict:
        deals = await asyncio.to_thread(self._mt5.history_deals_get, position=int(position_id))
        return {
            "deals": [
                {
                    "entryType": "DEAL_ENTRY_OUT" if d.entry in _DEAL_ENTRY_OUT_CODES else "DEAL_ENTRY_IN",
                    "time": datetime.fromtimestamp(d.time, tz=timezone.utc).isoformat(),
                    "price": d.price,
                    "profit": d.profit,
                }
                for d in (deals or [])
            ]
        }

    async def create_market_buy_order(self, symbol: str, lots: float, sl: float, tp: float, opts: dict) -> dict:
        return await self._send_market_order(symbol, "buy", lots, sl, tp, opts)

    async def create_market_sell_order(self, symbol: str, lots: float, sl: float, tp: float, opts: dict) -> dict:
        return await self._send_market_order(symbol, "sell", lots, sl, tp, opts)

    async def _send_market_order(self, symbol: str, direction: str, lots: float, sl: float, tp: float, opts: dict) -> dict:
        mt5 = self._mt5

        def _send() -> Any:
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                raise RuntimeError(f"symbol_info_tick({symbol}) returned None: {mt5.last_error()}")
            order_type = mt5.ORDER_TYPE_BUY if direction == "buy" else mt5.ORDER_TYPE_SELL
            price = tick.ask if direction == "buy" else tick.bid
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": lots,
                "type": order_type,
                "price": price,
                "sl": sl,
                "tp": tp,
                "deviation": 20,
                "magic": opts.get("magic", 0),
                "comment": opts.get("comment", ""),
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            result = mt5.order_send(request)
            if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
                code = getattr(result, "retcode", None)
                raise RuntimeError(f"order_send failed (retcode={code}): {mt5.last_error()}")
            return result

        result = await asyncio.to_thread(_send)
        return {"orderId": str(result.order)}

    async def close_position(self, position_id: str) -> None:
        mt5 = self._mt5

        def _close() -> None:
            positions = mt5.positions_get(ticket=int(position_id))
            if not positions:
                raise RuntimeError(f"position {position_id} not found for close")
            pos = positions[0]
            tick = mt5.symbol_info_tick(pos.symbol)
            if tick is None:
                raise RuntimeError(f"symbol_info_tick({pos.symbol}) returned None: {mt5.last_error()}")
            closing_type = mt5.ORDER_TYPE_SELL if pos.type == 0 else mt5.ORDER_TYPE_BUY
            price = tick.bid if pos.type == 0 else tick.ask
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": pos.symbol,
                "volume": pos.volume,
                "type": closing_type,
                "position": pos.ticket,
                "price": price,
                "deviation": 20,
                "magic": pos.magic,
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            result = mt5.order_send(request)
            if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
                code = getattr(result, "retcode", None)
                raise RuntimeError(f"close order_send failed (retcode={code}): {mt5.last_error()}")

        await asyncio.to_thread(_close)

    async def modify_position(self, position_id: str, sl: float, tp: float) -> None:
        mt5 = self._mt5

        def _modify() -> None:
            positions = mt5.positions_get(ticket=int(position_id))
            if not positions:
                raise RuntimeError(f"position {position_id} not found for modify")
            pos = positions[0]
            request = {
                "action": mt5.TRADE_ACTION_SLTP,
                "position": pos.ticket,
                "symbol": pos.symbol,
                "sl": sl,
                "tp": tp,
            }
            result = mt5.order_send(request)
            if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
                code = getattr(result, "retcode", None)
                raise RuntimeError(f"modify order_send failed (retcode={code}): {mt5.last_error()}")

        await asyncio.to_thread(_modify)
