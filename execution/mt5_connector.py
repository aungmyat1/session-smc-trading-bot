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

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

_log = logging.getLogger("strategy_demo.mt5_connector")

_SYNC_TIMEOUT_S    = 60
_RECONNECT_DELAY_S = 5
_HB_TIMEOUT_S      = 10   # fast ping timeout before deciding to reconnect
_LATENCY_PATH = Path("logs") / "latency_timeseries.jsonl"
_LATENCY_RETENTION = 1000

# Env var names as found in .env
_ACCOUNT_ID_VARS = {
    "demo": "VANTAGE_DEMO_METAAPI_ID",
    "live": "VANTAGE-LIVE-METAAPI-ID",
}


class MT5Connector:
    def __init__(self, mode: str = "demo") -> None:
        self._mode         = mode
        self._token        = os.environ.get("METAAPI_TOKEN", "")
        env_key            = _ACCOUNT_ID_VARS.get(mode, "VANTAGE_DEMO_METAAPI_ID")
        self._account_id   = os.environ.get(env_key, "")
        self._api          = None
        self._account      = None
        self._connection   = None
        self._last_hb:     datetime | None = None
        self._reconnecting = False     # guard against concurrent reconnect calls
        self._reconnect_count = 0
        self._last_reconnect_at = ""

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
        self._api     = MetaApi(self._token)
        self._account = await self._api.metatrader_account_api.get_account(self._account_id)

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
        import asyncio
        if self._reconnecting:
            _log.debug("Reconnect already in progress — skipping duplicate call")
            return
        self._reconnecting = True
        try:
            self._reconnect_count += 1
            self._last_reconnect_at = datetime.now(timezone.utc).isoformat()
            _log.warning("Reconnecting to MetaAPI…")
            await self.disconnect()
            await asyncio.sleep(_RECONNECT_DELAY_S)
            await self.connect()
        finally:
            self._reconnecting = False

    async def ensure_connected(self) -> bool:
        """
        Lightweight liveness check. Returns True if already alive, False after
        a successful reconnect. Raises if reconnect also fails.
        Fast-path: a timed get_account_information call proves the socket works.
        """
        import asyncio
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
            payload = {
                "connected":      True,
                "latency_ms":     latency,
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
