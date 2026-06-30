#!/usr/bin/env python3
"""
Configure and deploy MetaAPI account 026ea073-5241-4d53-9a87-b0cb791443af.

Steps:
  1  Load credentials from .env
  2  Fetch account (currently in DRAFT state)
  3  Update with MT5 password (login + server already set)
  4  Deploy account
  5  Wait for synchronization
  6  Update .env METAAPI_ACCOUNT_ID → new account
  7  Confirm with a quick connection test
"""

import asyncio
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv

load_dotenv(_ROOT / ".env")

NEW_ACCOUNT_ID = "026ea073-5241-4d53-9a87-b0cb791443af"
_TOKEN = os.getenv("METAAPI_TOKEN", "")
_PASSWORD = os.getenv("VANTAGE_MT5_PASSWORD", "")


async def main() -> None:
    if not _TOKEN:
        print("❌ METAAPI_TOKEN not set in .env")
        sys.exit(1)
    if not _PASSWORD:
        print("❌ VANTAGE_MT5_PASSWORD not set in .env")
        sys.exit(1)

    from metaapi_cloud_sdk import MetaApi

    print(f"\nConfiguring MetaAPI account: {NEW_ACCOUNT_ID}")
    print("=" * 60)

    api = MetaApi(_TOKEN)

    # ── Step 1: Fetch account ─────────────────────────────────────
    print("[1] Fetching account…")
    account = await api.metatrader_account_api.get_account(NEW_ACCOUNT_ID)
    print(f"    state={account.state}  server={account.server}  login={account.login}")

    # ── Step 2: Set password (account is in DRAFT — login/server already set) ──
    print("[2] Setting MT5 password…")
    await account.update({"password": _PASSWORD})
    print("    password updated")

    # ── Step 3: Deploy ────────────────────────────────────────────
    print("[3] Deploying account…")
    await account.deploy()
    print("    deploy initiated — waiting for DEPLOYED state (up to 5 min)…")

    # ── Step 4: Wait deployed ─────────────────────────────────────
    await account.wait_deployed(timeout_in_seconds=300)
    await account.reload()
    print(f"    state={account.state}")

    # ── Step 5: Wait connected (broker sync) ─────────────────────
    print("[4] Waiting for broker connection…")
    await account.wait_connected(timeout_in_seconds=120)
    await account.reload()
    print(f"    connectionStatus={account.connection_status}")

    # ── Step 6: Quick RPC test ────────────────────────────────────
    print("[5] Verifying RPC connection…")
    conn = account.get_rpc_connection()
    await conn.connect()
    await conn.wait_synchronized(60)
    info = await conn.get_account_information()
    print(
        f"    balance={info.get('balance')} {info.get('currency')}  equity={info.get('equity')}"
    )
    await conn.close()

    print("\n" + "=" * 60)
    print(f"✅ Account configured and connected.")
    print(f"   Account ID : {NEW_ACCOUNT_ID}")
    print(f"   Server     : {account.server}")
    print(f"   Login      : {account.login}")
    print(f"   Balance    : {info.get('balance')} {info.get('currency')}")
    print("=" * 60)

    # ── Step 7: Update .env ───────────────────────────────────────
    env_path = _ROOT / ".env"
    env_text = env_path.read_text()
    old_line = f"METAAPI_ACCOUNT_ID=21649455-718b-494b-8f34-ed54fde80b5d"
    new_line = f"METAAPI_ACCOUNT_ID={NEW_ACCOUNT_ID}"
    if old_line in env_text:
        env_path.write_text(env_text.replace(old_line, new_line))
        print(f"\n.env updated: METAAPI_ACCOUNT_ID → {NEW_ACCOUNT_ID}")
    elif NEW_ACCOUNT_ID in env_text:
        print(f"\n.env already has METAAPI_ACCOUNT_ID={NEW_ACCOUNT_ID}")
    else:
        print(
            f"\n⚠️  Could not auto-update .env — set manually: METAAPI_ACCOUNT_ID={NEW_ACCOUNT_ID}"
        )

    api.close()
    print("\nDone. Run: python3 scripts/validate_connection.py")


if __name__ == "__main__":
    asyncio.run(main())
