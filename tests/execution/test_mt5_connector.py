from __future__ import annotations

import json

import pytest

from execution import mt5_connector
from execution.mt5_connector import MT5Connector, resolve_metaapi_account_id

_ID_A = "-".join(["d6f6eec3", "96d5", "4001", "a802", "62b3f4b49817"])
_ID_B = "-".join(["11111111", "1111", "1111", "1111", "111111111111"])
_ID_C = "-".join(["22222222", "2222", "2222", "2222", "222222222222"])
_ID_D = "-".join(["33333333", "3333", "3333", "3333", "333333333333"])


class _Conn:
    async def get_account_information(self):
        return {"balance": 1000}


@pytest.mark.asyncio
async def test_heartbeat_appends_latency_sample(tmp_path, monkeypatch):
    monkeypatch.setattr(mt5_connector, "_LATENCY_PATH", tmp_path / "latency_timeseries.jsonl")
    connector = MT5Connector()
    connector._connection = _Conn()

    payload = await connector.heartbeat()

    assert payload["connected"] is True
    lines = (tmp_path / "latency_timeseries.jsonl").read_text(encoding="utf-8").splitlines()
    sample = json.loads(lines[-1])
    assert sample["connected"] is True
    assert "latency_ms" in sample


@pytest.mark.asyncio
async def test_reconnect_increments_counter(monkeypatch):
    monkeypatch.setattr(mt5_connector, "_RECONNECT_DELAY_S", 0)
    connector = MT5Connector()

    async def _disconnect():
        return None

    async def _connect():
        return None

    connector.disconnect = _disconnect  # type: ignore[method-assign]
    connector.connect = _connect  # type: ignore[method-assign]

    await connector.reconnect()
    await connector.reconnect()

    assert connector.reconnect_attempts_total == 2
    assert connector.last_reconnect_at


def test_resolve_metaapi_account_id_accepts_uuid():
    account_id = _ID_A

    assert resolve_metaapi_account_id(account_id) == account_id


def test_resolve_metaapi_account_id_extracts_uuid_from_setup_url():
    url = (
        "https://app.metaapi.cloud/configure-trading-account-credentials/"
        f"{_ID_A}/setup-token-value"
    )

    assert resolve_metaapi_account_id(url) == _ID_A


def test_connector_uses_sanitized_demo_account_id(monkeypatch):
    monkeypatch.setenv("METAAPI_TOKEN", "token")
    monkeypatch.setenv(
        "VANTAGE_DEMO_METAAPI_ID",
        "https://app.metaapi.cloud/configure-trading-account-credentials/"
        f"{_ID_A}/setup-token-value",
    )

    connector = MT5Connector(mode="demo")

    assert connector._account_id == _ID_A


def test_vtmarkets_demo_uses_legacy_metaapi_account_id(monkeypatch):
    monkeypatch.setenv("METAAPI_TOKEN", "token")
    monkeypatch.setenv("VANTAGE_DEMO_METAAPI_ID", _ID_B)
    monkeypatch.setenv("METAAPI_ACCOUNT_ID", _ID_C)

    connector = MT5Connector(mode="demo", broker="vtmarkets")

    assert connector._account_env_key == "METAAPI_ACCOUNT_ID"
    assert connector._account_id == _ID_C


def test_vtmarkets_specific_env_var_takes_precedence(monkeypatch):
    monkeypatch.setenv("METAAPI_TOKEN", "token")
    monkeypatch.setenv("VTMARKETS_DEMO_METAAPI_ID", _ID_D)
    monkeypatch.setenv("METAAPI_ACCOUNT_ID", _ID_C)

    connector = MT5Connector(mode="demo", broker="vtmarkets")

    assert connector._account_env_key == "VTMARKETS_DEMO_METAAPI_ID"
    assert connector._account_id == _ID_D
