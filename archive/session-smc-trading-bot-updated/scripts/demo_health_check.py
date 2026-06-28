"""
ST-A2 Demo Health Check — single-shot status report.

Usage:
    python3 scripts/demo_health_check.py
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

from execution.mt5_connector import MT5Connector
from execution.vantage_demo_executor import VantageDemoExecutor
from execution.trade_manager import TradeManager
from execution.trade_journal import DemoTradeJournal

_JOURNAL_PATH  = _ROOT / "logs" / "st_a2_demo_trades.jsonl"
_SIGNAL_LOG    = _ROOT / "logs" / "st_a2_demo.log"
_DAILY_LOSS_LIMIT = 0.015
_MAX_TRADES    = 4


def _last_signal() -> str:
    if not _SIGNAL_LOG.exists():
        return "no log"
    lines = _SIGNAL_LOG.read_text().splitlines()
    for line in reversed(lines):
        if "SIGNAL" in line:
            return line.strip()[-120:]
    return "no signal yet"


def _daily_pnl(journal: DemoTradeJournal) -> tuple[float, int]:
    today = datetime.now(timezone.utc).date().isoformat()
    total_r = 0.0
    count   = 0
    for t in journal.read_all():
        if t.get("type") == "CLOSE" and t.get("timestamp", "")[:10] == today:
            total_r += t.get("result_R", 0.0)
            count   += 1
    return total_r, count


async def _check() -> None:
    connector = MT5Connector(mode="demo")
    try:
        await connector.connect()
    except Exception as exc:
        print(f"\n[BLOCKED] {exc}")
        return

    executor = VantageDemoExecutor(connector)
    manager  = TradeManager(executor)
    journal  = DemoTradeJournal()

    try:
        hb   = await connector.heartbeat()
        acct = await executor.get_account_info()
        pos  = await manager.get_positions()
        summ = journal.summary()
    except Exception as exc:
        print(f"[ERROR] {exc}")
        return
    finally:
        await connector.disconnect()

    daily_r, daily_count = _daily_pnl(journal)
    balance = acct["balance"]
    equity  = acct["equity"]
    daily_pnl_pct = daily_r * 0.0025  # approx in % (each R = 0.25%)
    dd_used = abs(min(0.0, daily_pnl_pct)) / _DAILY_LOSS_LIMIT * 100

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    ok  = hb["connected"]

    print()
    print("=" * 54)
    print(f"  ST-A2 DEMO HEALTH CHECK   {now}")
    print("=" * 54)

    # MetaAPI
    icon = "🟢" if ok else "🔴"
    print(f"\n  MetaAPI:       {icon} {'OK' if ok else 'DOWN'}  latency={hb['latency_ms']}ms")
    print(f"  Last HB:       {hb['last_heartbeat']}")

    # Account
    print(f"\n  Balance:       ${balance:,.2f}  |  Equity: ${equity:,.2f}")
    free = acct['free_margin']
    print(f"  Free margin:   ${free:,.2f}")

    # Positions
    print(f"\n  Open trades:   {len(pos)}")
    for p in pos:
        print(f"    {p['symbol']:8s} {p['direction'].upper():5s} "
              f"{p['lots']}lot  entry={p['entry']}  P&L={p['profit']:+.2f}")

    # Daily
    dd_bar = "#" * int(dd_used / 10) + "." * (10 - int(dd_used / 10))
    print(f"\n  Daily trades:  {daily_count}/{_MAX_TRADES}")
    print(f"  Daily P/L:     {daily_r:+.2f}R  ({daily_pnl_pct:+.3%})")
    print(f"  DD used:       [{dd_bar}] {dd_used:.0f}% of 1.5% limit")

    # Journal
    print(f"\n  All trades:    opened={summ['total_opened']}  "
          f"closed={summ['total_closed']}  "
          f"W={summ['wins']}  L={summ['losses']}  avgR={summ['avg_r']:.3f}")

    # Last signal
    print(f"\n  Last signal:   {_last_signal()}")

    # Status verdict
    issues = []
    if not ok:
        issues.append("MetaAPI disconnected")
    if daily_count >= _MAX_TRADES:
        issues.append("daily trade limit reached")
    if dd_used >= 100:
        issues.append("daily loss limit hit")

    print()
    if issues:
        print(f"  STATUS:  🔴 ISSUES — {', '.join(issues)}")
    else:
        print("  STATUS:  🟢 HEALTHY")
    print("=" * 54)
    print()


def main() -> None:
    asyncio.run(_check())


if __name__ == "__main__":
    main()
