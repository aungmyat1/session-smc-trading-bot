#!/usr/bin/env python3
"""Compare broker positions with the SQLite trade journal."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from core.trade_journal_db import TradeJournalDB
from execution.mt5_connector import MT5Connector
from execution.vantage_demo_executor import VantageDemoExecutor
from monitoring.telegram import TelegramAlerter
from production.engine import MANAGED_POSITION_MAGIC

# Compatibility alias retained for older operational tests and scripts.
_MAGIC = MANAGED_POSITION_MAGIC


def _summarize(orphan_positions: list[dict], stale_trades: list[dict]) -> str:
    lines: list[str] = []
    if orphan_positions:
        lines.append(
            "orphan_broker_positions="
            + ", ".join(f"{item.get('symbol')}:{item.get('id')}" for item in orphan_positions)
        )
    if stale_trades:
        lines.append(
            "stale_db_trades="
            + ", ".join(f"{item.get('symbol')}:{item.get('broker_order_id')}" for item in stale_trades)
        )
    return "\n".join(lines) if lines else "in_sync"


async def run(*, dry_run: bool = False) -> int:
    connector = MT5Connector(mode="demo")
    await connector.connect()
    try:
        executor = VantageDemoExecutor(connector)
        db = TradeJournalDB()
        broker_positions = [p for p in await executor.get_positions() if p.get("magic") == MANAGED_POSITION_MAGIC]
        open_trades = db.get_open_trades()

        broker_keys = {
            (
                str(item.get("symbol", "")),
                str(item.get("id", "")),
                str(item.get("direction", "")),
            )
            for item in broker_positions
        }
        trade_keys = {
            (
                str(item.get("symbol", "")),
                str(item.get("broker_order_id", "")),
                "buy" if str(item.get("direction", "")).lower() == "long" else "sell",
            )
            for item in open_trades
        }

        orphan_positions = [
            item for item in broker_positions
            if (str(item.get("symbol", "")), str(item.get("id", "")), str(item.get("direction", ""))) not in trade_keys
        ]
        stale_trades = [
            item for item in open_trades
            if (
                str(item.get("symbol", "")),
                str(item.get("broker_order_id", "")),
                "buy" if str(item.get("direction", "")).lower() == "long" else "sell",
            ) not in broker_keys
        ]

        summary = _summarize(orphan_positions, stale_trades)
        if summary == "in_sync":
            print("Reconciliation OK: broker and SQLite journal are in sync.")
            return 0

        print("Reconciliation mismatch detected:")
        print(summary)
        if not dry_run:
            telegram = TelegramAlerter(
                token=os.getenv("TELEGRAM_BOT_TOKEN"),
                chat_id=os.getenv("TELEGRAM_CHAT_ID"),
            )
            await telegram.send_reconciliation_mismatch(summary)
            await telegram.stop()
        return 1
    finally:
        await connector.disconnect()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Log only; do not send Telegram alerts")
    args = parser.parse_args()
    return asyncio.run(run(dry_run=args.dry_run))


if __name__ == "__main__":
    raise SystemExit(main())
