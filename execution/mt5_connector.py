"""
MT5 Connector — MetaAPI connection for Vantage demo OR live account.

Env vars resolved from .env (actual keys found in project):
    METAAPI_TOKEN              — MetaAPI platform token (shared)
    VANTAGE_DEMO_METAAPI_ID    — MetaAPI account ID for Vantage DEMO
                                  (provision once via MetaAPI dashboard using
                                   VANTAGE_MT5_DEMO_LOGIN / VANTAGE_MT5_DEMO_PASSWORD
                                   / VANTAGE_MT5_DEMO-SERVER, then paste the UUID here)
    VANTAGE-LIVE-METAAPI-ID    — MetaAPI account ID for Vantage LIVE
    DEMO_ONLY                  — true (default) = no write orders sent

Public API:
    MT5Connector(mode="demo")  mode: "demo" | "live"
        async .connect()
        async .disconnect()
        async .reconnect()
        async .heartbeat() -> dict
        .connection          — raw MetaAPI RPC connection
        .is_connected        -> bool
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

_log = logging.getLogger("strategy_demo.mt5_connector")

_SYNC_TIMEOUT_S = 60
_RECONNECT_DELAY_S = 5

# Env var names as found in .env
_ACCOUNT_ID_VARS = {
    "demo": "VANTAGE_DEMO_METAAPI_ID",
    "live": "VANTAGE-LIVE-METAAPI-ID",
}


class MT5Connector:
    def __init__(self, mode: str = "demo") -> None:
        self._mode = mode
        self._token = os.environ.get("METAAPI_TOKEN", "")
        env_key = _ACCOUNT_ID_VARS.get(mode, "VANTAGE_DEMO_METAAPI_ID")
        self._account_id = os.environ.get(env_key, "")
        self._api = None
        self._account = None
        self._connection = None
        self._last_hb: datetime | None = None

    # ── Connection ─────────────────────────────────────────────────────────

    async def connect(self) -> None:
        env_key = _ACCOUNT_ID_VARS.get(self._mode, "VANTAGE_DEMO_METAAPI_ID")
        if not self._token:
            raise RuntimeError("METAAPI_TOKEN not set in .env")
        if not self._account_id:
            raise RuntimeError(
                f"{env_key} not set in .env.\n"
                f"Steps to get it:\n"
                f"  1. Go to https://app.metaapi.cloud → Accounts → Add account\n"
                f"  2. Enter VANTAGE_MT5_DEMO_LOGIN / VANTAGE_MT5_DEMO_PASSWORD / VANTAGE_MT5_DEMO-SERVER\n"
                f"  3. Copy the account UUID → add to .env as VANTAGE_DEMO_METAAPI_ID=<uuid>"
            )
        try:
            from metaapi_cloud_sdk import MetaApi
        except ImportError:
            raise RuntimeError("pip install metaapi-cloud-sdk>=29")

        _log.info("Connecting to Vantage demo (account=%s)…", self._account_id)
        self._api = MetaApi(self._token)
        self._account = await self._api.metatrader_account_api.get_account(
            self._account_id
        )

        if self._account.state not in ("DEPLOYING", "DEPLOYED"):
            _log.info("Deploying account…")
            await self._account.deploy()

        await self._account.wait_connected()
        self._connection = self._account.get_rpc_connection()
        await self._connection.connect()
        await self._connection.wait_synchronized(_SYNC_TIMEOUT_S)  # int, not dict
        self._last_hb = datetime.now(timezone.utc)
        _log.info("Connected to Vantage MT5 demo.")

    async def disconnect(self) -> None:
        if self._connection:
            try:
                await self._connection.close()
            except Exception:
                pass
        if self._api:
            try:
                self._api.close()
            except Exception:
                pass
        self._connection = None
        _log.info("Disconnected.")

    async def reconnect(self) -> None:
        _log.warning("Reconnecting…")
        await self.disconnect()
        import asyncio

        await asyncio.sleep(_RECONNECT_DELAY_S)
        await self.connect()

    # ── Heartbeat ──────────────────────────────────────────────────────────

    async def heartbeat(self) -> dict:
        """
        Ping the broker. Returns {connected, latency_ms, last_heartbeat}.
        Attempts reconnect if check fails.
        """
        import time

        t0 = time.monotonic()
        try:
            await self._connection.get_account_information()
            latency = round((time.monotonic() - t0) * 1000)
            self._last_hb = datetime.now(timezone.utc)
            return {
                "connected": True,
                "latency_ms": latency,
                "last_heartbeat": self._last_hb.isoformat(),
            }
        except Exception as exc:
            _log.warning("Heartbeat failed: %s — reconnecting", exc)
            try:
                await self.reconnect()
                return {
                    "connected": True,
                    "latency_ms": -1,
                    "last_heartbeat": (
                        self._last_hb.isoformat() if self._last_hb else ""
                    ),
                }
            except Exception:
                return {"connected": False, "latency_ms": -1, "last_heartbeat": ""}

    @property
    def is_connected(self) -> bool:
        return self._connection is not None

    @property
    def connection(self):
        return self._connection
