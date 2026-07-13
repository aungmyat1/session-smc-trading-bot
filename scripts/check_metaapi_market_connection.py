#!/usr/bin/env python3
"""Read-only MetaAPI/VT Markets market connection check."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(_ROOT / ".env")
except ImportError:
    pass

from execution.mt5_connector import MT5Connector, resolve_metaapi_account_id
from execution.vantage_demo_executor import VantageDemoExecutor


async def _run(symbol: str, timeframe: str, count: int, account_url: str | None, broker: str) -> int:
    if os.getenv("LIVE_TRADING", "false").strip().lower() in {"true", "1", "yes"}:
        print("FAIL: LIVE_TRADING must remain false for this check")
        return 2
    if account_url:
        account_id = resolve_metaapi_account_id(account_url)
        if account_id == account_url:
            print("FAIL: --account-url must be a MetaAPI setup URL containing an account UUID")
            return 2
        if broker == "vtmarkets":
            os.environ["VTMARKETS_DEMO_METAAPI_ID"] = account_id
        else:
            os.environ["VANTAGE_DEMO_METAAPI_ID"] = account_id

    connector = MT5Connector(mode="demo", broker=broker)
    executor = VantageDemoExecutor(connector)
    try:
        await connector.connect()
        account = await executor.get_account_info()
        price = await executor.get_price(symbol)
        candles = await executor.get_candles(symbol, timeframe, count)
        print("PASS: MetaAPI demo market connection is healthy")
        print(f"account_currency={account['currency']} equity={account['equity']:.2f}")
        print(f"{symbol} bid={price['bid']} ask={price['ask']} spread_pips={price['spread_pips']}")
        print(f"{symbol} {timeframe} candles={len(candles)}")
        return 0 if candles else 1
    except Exception as exc:
        detail = str(exc) or exc.__class__.__name__
        print(f"FAIL: MetaAPI demo market connection failed: {detail}")
        return 1
    finally:
        await connector.disconnect()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", default="EURUSD")
    parser.add_argument("--timeframe", default="M15")
    parser.add_argument("--count", type=int, default=20)
    parser.add_argument("--broker", choices=["vantage", "vtmarkets"], default="vtmarkets")
    parser.add_argument(
        "--account-url",
        default=None,
        help="Optional MetaAPI configure-trading-account-credentials URL; only the UUID is used.",
    )
    args = parser.parse_args()
    return asyncio.run(_run(args.symbol.upper(), args.timeframe, args.count, args.account_url, args.broker))


if __name__ == "__main__":
    raise SystemExit(main())
