"""
Demo Status — display MT5 connection + account + trade state.

Usage:
    python3 scripts/demo_status.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(_ROOT / ".env")
except ImportError:
    pass

from execution.mt5_connector import MT5Connector
from execution.vantage_demo_executor import VantageDemoExecutor
from execution.trade_manager import TradeManager
from execution.trade_journal import DemoTradeJournal


async def _status() -> None:
    connector = MT5Connector(mode="demo")
    try:
        await connector.connect()
    except Exception as exc:
        print(f"\n[BLOCKED] Connection failed: {exc}")
        print("Check METAAPI_TOKEN and VANTAGE_ACCOUNT_ID in .env")
        return

    executor = VantageDemoExecutor(connector)
    manager = TradeManager(executor)
    journal = DemoTradeJournal()

    try:
        hb = await connector.heartbeat()
        acct = await executor.get_account_info()
        pos = await manager.get_positions()
        summ = journal.summary()
    except Exception as exc:
        print(f"[ERROR] Status fetch failed: {exc}")
        return
    finally:
        await connector.disconnect()

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print()
    print("=" * 50)
    print(f"  ST-A2 DEMO STATUS   {now}")
    print("=" * 50)

    # Connection
    status_icon = "🟢" if hb["connected"] else "🔴"
    print(
        f"\n  CONNECTION:    {status_icon}  {'OK' if hb['connected'] else 'DISCONNECTED'}"
    )
    print(f"  Latency:       {hb['latency_ms']} ms")
    print(f"  Last HB:       {hb['last_heartbeat']}")

    # Account
    print(f"\n  ACCOUNT")
    print(f"  Balance:       {acct['balance']:.2f} {acct['currency']}")
    print(f"  Equity:        {acct['equity']:.2f} {acct['currency']}")
    print(f"  Free margin:   {acct['free_margin']:.2f} {acct['currency']}")

    # Open positions
    print(f"\n  OPEN POSITIONS: {len(pos)}")
    for p in pos:
        print(
            f"    {p['symbol']} {p['direction'].upper()} "
            f"{p['lots']}lot  entry={p['entry']}  P&L={p['profit']:.2f}"
        )

    # Journal summary
    print(f"\n  JOURNAL SUMMARY")
    print(f"  Total opened:  {summ['total_opened']}")
    print(f"  Total closed:  {summ['total_closed']}")
    print(f"  Wins:          {summ['wins']}")
    print(f"  Losses:        {summ['losses']}")
    print(f"  Avg R:         {summ['avg_r']:.3f}")

    print()
    print("=" * 50)


def main() -> None:
    asyncio.run(_status())


if __name__ == "__main__":
    main()
