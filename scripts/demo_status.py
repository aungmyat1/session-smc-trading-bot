"""
Demo Status — display MT5 connection + account + trade state.

Usage:
    python3 scripts/demo_status.py
"""

from __future__ import annotations

import asyncio
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

from execution.mt5_connector import MT5Connector  # noqa: E402
from execution.vantage_demo_executor import VantageDemoExecutor  # noqa: E402
from execution.trade_manager import TradeManager  # noqa: E402
from execution.trade_journal import DemoTradeJournal  # noqa: E402

_CONNECT_TIMEOUT_S = 45
_RPC_TIMEOUT_S = 20


async def _status() -> None:
    connector = MT5Connector(mode="demo")
    try:
        await asyncio.wait_for(connector.connect(), timeout=_CONNECT_TIMEOUT_S)
    except Exception as exc:
        print(f"\n[BLOCKED] Connection failed: {exc}")
        print("Check METAAPI_TOKEN and VANTAGE_ACCOUNT_ID in .env")
        return

    executor = VantageDemoExecutor(connector)
    manager = TradeManager(executor)
    journal = DemoTradeJournal()

    try:
        hb = await asyncio.wait_for(connector.heartbeat(), timeout=_RPC_TIMEOUT_S)
        acct = await asyncio.wait_for(
            executor.get_account_info(), timeout=_RPC_TIMEOUT_S
        )
        pos = await asyncio.wait_for(manager.get_positions(), timeout=_RPC_TIMEOUT_S)
        summ = journal.summary()
    except Exception as exc:
        print(f"[ERROR] Status fetch failed: {exc}")
        return
    finally:
        await connector.disconnect()

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print()
    print("=" * 50)
    print(f"  STRATEGY DEMO STATUS   {now}")
    print("=" * 50)

    # Connection
    status_icon = "🟢" if hb["connected"] else "🔴"
    print(
        f"\n  CONNECTION:    {status_icon}  {'OK' if hb['connected'] else 'DISCONNECTED'}"
    )
    print(f"  Latency:       {hb['latency_ms']} ms")
    print(f"  Last HB:       {hb['last_heartbeat']}")

    # Account
    print("\n  ACCOUNT")
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
    print("\n  JOURNAL SUMMARY")
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
