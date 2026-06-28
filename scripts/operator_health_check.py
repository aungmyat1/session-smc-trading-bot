#!/usr/bin/env python3
"""
operator_health_check.py — Comprehensive operator health check CLI.

Checks governance lifecycle, bot state, log freshness, and credentials.

Usage:
    python scripts/operator_health_check.py
    python scripts/operator_health_check.py --json
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logging.basicConfig(level=logging.WARNING)
_UTC = timezone.utc


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Operator health check")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.add_argument("--strategy-id", default="ST-A2")
    return p.parse_args()


def check_governance(strategy_id: str) -> dict:
    try:
        from session_smc.governance import StrategyRegistry
        reg = StrategyRegistry(registry_path=Path("data/strategy_registry.json"))
        if strategy_id in reg.list_strategies():
            state = reg.get_state(strategy_id)
            return {"ok": True, "state": state.value}
        return {"ok": True, "state": "not_registered", "note": "Not yet in registry"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def check_bot_state() -> dict:
    state_file = Path("logs/bot_state.json")
    if not state_file.exists():
        return {"ok": True, "state": "no_state_file", "note": "Bot has not run yet"}
    try:
        data = json.loads(state_file.read_text())
        return {
            "ok": not data.get("halted", False),
            "halted": data.get("halted", False),
            "halt_reason": data.get("halt_reason", ""),
            "daily_loss_r": data.get("daily_loss_r", 0.0),
            "consecutive_losses": data.get("consecutive_losses", 0),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def check_log_freshness() -> dict:
    log_file = Path("logs/bot.jsonl")
    if not log_file.exists():
        return {"ok": True, "note": "Log file not yet created"}
    stat = log_file.stat()
    age_s = datetime.now(_UTC).timestamp() - stat.st_mtime
    return {
        "ok": True,
        "last_modified_age_s": round(age_s, 1),
        "path": str(log_file),
    }


def check_credentials() -> dict:
    token = os.environ.get("METAAPI_TOKEN", "")
    account_id = os.environ.get("METAAPI_ACCOUNT_ID", "")
    telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    return {
        "ok": bool(token and account_id),
        "metaapi_token_set": bool(token),
        "metaapi_account_id_set": bool(account_id),
        "telegram_configured": bool(telegram_token),
    }


def main() -> None:
    args = parse_args()
    report = {
        "timestamp": datetime.now(_UTC).isoformat(),
        "strategy_id": args.strategy_id,
        "governance": check_governance(args.strategy_id),
        "bot_state": check_bot_state(),
        "log_freshness": check_log_freshness(),
        "credentials": check_credentials(),
    }
    overall_ok = all(
        v.get("ok", True)
        for v in report.values()
        if isinstance(v, dict)
    )
    report["overall_ok"] = overall_ok

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"\n=== Operator Health Check: {args.strategy_id} @ {report['timestamp']} ===\n")
        for section, data in report.items():
            if section in ("timestamp", "strategy_id", "overall_ok"):
                continue
            if not isinstance(data, dict):
                continue
            status = "OK" if data.get("ok", True) else "WARN"
            print(f"  [{status}] {section}:")
            for k, v in data.items():
                if k == "ok":
                    continue
                print(f"        {k}: {v}")
        print(f"\n  Overall: {'HEALTHY' if overall_ok else 'DEGRADED'}\n")

    sys.exit(0 if overall_ok else 1)


if __name__ == "__main__":
    main()
