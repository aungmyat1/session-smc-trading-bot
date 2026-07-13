"""
MT5 Connector — MetaAPI connection for MT5 demo accounts.

Env vars resolved from .env (actual keys found in project):
    METAAPI_TOKEN              — MetaAPI platform token (shared)
    VTMARKETS_DEMO_METAAPI_ID  — MetaAPI account ID for VT Markets DEMO
    VT_MARKETS_DEMO_METAAPI_ID — compatibility spelling for VT Markets DEMO
    METAAPI_ACCOUNT_ID         — legacy VT Markets demo account ID
    VANTAGE_DEMO_METAAPI_ID    — legacy compatibility account ID
                                  (provision once via MetaAPI dashboard using
                                   the selected demo MT5 login / password / server,
                                   then paste the UUID here)
    VANTAGE-LIVE-METAAPI-ID    — legacy live key; live is not configured for agents
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
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

_log = logging.getLogger("strategy_demo.mt5_connector")

_SYNC_TIMEOUT_S    = 60
_RECONNECT_DELAY_S = 5
_HB_TIMEOUT_S      = 10   # fast ping timeout before deciding to reconnect
_LATENCY_PATH = Path("logs") / "latency_timeseries.jsonl"
_LATENCY_RETENTION = 1000

# Env var names as found in .env. The first present key wins.
_ACCOUNT_ID_VARS = {
    ("vantage", "demo"): ("VANTAGE_DEMO_METAAPI_ID",),
    ("vantage", "live"): ("VANTAGE-LIVE-METAAPI-ID", "VANTAGE_LIVE_METAAPI_ID"),
    ("vtmarkets", "demo"): (
        "VTMARKETS_DEMO_METAAPI_ID",
        "VT_MARKETS_DEMO_METAAPI_ID",
        "METAAPI_ACCOUNT_ID",
    ),
}

_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def resolve_metaapi_account_id(raw: str) -> str:
    """Return a MetaAPI account UUID from either a UUID or setup URL."""
    value = (raw or "").strip()
    if not value:
        return ""
    if _UUID_RE.match(value):
        return value

    parsed = urlparse(value)
    if parsed.netloc.lower() != "app.metaapi.cloud":
        return value
    parts = [part for part in parsed.path.split("/") if part]
    for part in parts:
        if _UUID_RE.match(part):
            return part
    return value


def _redacted_account_marker(account_id: str) -> str:
    return "configured" if account_id else "missing"


class MT5Connector:
    def __init__(self, mode: str = "demo", broker: str = "vtmarkets") -> None:
        self._mode         = mode
        self._broker       = broker.lower().replace("-", "").replace("_", "")
        self._token        = os.environ.get("METAAPI_TOKEN", "")
        env_keys           = self._account_env_keys()
        self._account_env_key, raw_account_id = self._first_env_value(env_keys)
        self._account_id   = resolve_metaapi_account_id(raw_account_id)
        self._api          = None
        self._account      = None
        self._connection   = None
        self._last_hb:     datetime | None = None
        self._reconnecting = False     # guard against concurrent reconnect calls
        self._reconnect_count = 0
        self._last_reconnect_at = ""

    # ── Connection ─────────────────────────────────────────────────────────

    async def connect(self) -> None:
        import asyncio

        if not self._token:
            raise RuntimeError("METAAPI_TOKEN not set in .env")
        if not self._account_id:
            raise RuntimeError(
                f"{' or '.join(self._account_env_keys())} not set in .env.\n"
                f"Steps to get it:\n"
                f"  1. Go to https://app.metaapi.cloud → Accounts → Add account\n"
                f"  2. Enter the selected demo MT5 login / password / server\n"
                f"  3. Copy the account UUID → add it to .env"
            )
        try:
            from metaapi_cloud_sdk import MetaApi
        except ImportError:
            raise RuntimeError("pip install metaapi-cloud-sdk>=29")

        _log.info(
            "Connecting to %s %s (account=%s)…",
            self._broker,
            self._mode,
            _redacted_account_marker(self._account_id),
        )
        self._api     = MetaApi(self._token)
        self._account = await self._api.metatrader_account_api.get_account(self._account_id)

        if self._account.state not in ("DEPLOYING", "DEPLOYED"):
            _log.info("Deploying account…")
            await self._account.deploy()

        await asyncio.wait_for(self._account.wait_connected(), timeout=_SYNC_TIMEOUT_S)
        self._connection = self._account.get_rpc_connection()
        await self._connection.connect()
        await asyncio.wait_for(
            self._connection.wait_synchronized(_SYNC_TIMEOUT_S), timeout=_SYNC_TIMEOUT_S + 5
        )
        self._last_hb = datetime.now(timezone.utc)
        _log.info("Connected to %s MT5 %s.", self._broker, self._mode)

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

    def _account_env_keys(self) -> tuple[str, ...]:
        key = (self._broker, self._mode)
        if key not in _ACCOUNT_ID_VARS:
            raise ValueError(f"Unsupported MetaAPI account mapping for broker={self._broker!r} mode={self._mode!r}")
        return _ACCOUNT_ID_VARS[key]

    @staticmethod
    def _first_env_value(env_keys: tuple[str, ...]) -> tuple[str, str]:
        for env_key in env_keys:
            value = os.environ.get(env_key, "")
            if value:
                return env_key, value
        return env_keys[0], ""

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
