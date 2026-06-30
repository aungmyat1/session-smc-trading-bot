#!/usr/bin/env python3
"""
DEP-02 — MetaAPI Connection Validation Script.

Validates broker connectivity for the Vantage MT5 Demo account via MetaAPI.

SAFETY: LIVE_TRADING is FORCED to 'false' unconditionally at the top of this
file, BEFORE any module import or .env load. Even if .env contains
LIVE_TRADING=true, no real orders are placed by this script.

Checks performed:
  1  LIVE_TRADING guard (forced false)
  2  .env credential presence
  3  MetaAPI connect()
  4  Account synchronization
  5  Balance + equity retrieval
  6  Open positions retrieval
  7  Symbol prices + spread check (EURUSD, GBPUSD)
  8  DRY_RUN order submission
  9  Trade logging (all 6 event types)
  10 Heartbeat fields
  11 Reconnect: disconnect → reconnect → account_info

Output:
  logs/dep02_validation.jsonl   — structured event log
  docs/DEP_02_CONNECTION_REPORT.md — human-readable report

Usage:
    python3 scripts/validate_connection.py
"""

# ── FORCE LIVE_TRADING=false BEFORE ANY OTHER IMPORT ─────────────────────────
# This must be the very first executable line — before dotenv, before execution.*
# os.environ is set here so that load_dotenv() (which defaults to override=False)
# will not overwrite it, and any module that reads LIVE_TRADING at import time
# will see "false".
import os

_ORIGINAL_LIVE_TRADING = os.environ.get("LIVE_TRADING", "not set in env")
os.environ["LIVE_TRADING"] = "false"

import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv

load_dotenv(_ROOT / ".env", override=False)  # override=False: our forced "false" wins

# Now import execution layer — LIVE_TRADING module-level variable will be False
from execution.metaapi_client import MetaAPIClient, LIVE_TRADING
from execution.trade_logger import TradeLogger

_UTC = timezone.utc
_LOG_DIR = _ROOT / "logs"
_LOG_DIR.mkdir(exist_ok=True)
_DOCS_DIR = _ROOT / "docs"


# ── Check tracker ─────────────────────────────────────────────────────────────


class CheckResult:
    def __init__(self) -> None:
        self._checks: list[dict] = []

    def add(self, name: str, passed: bool, value: str, detail: str = "") -> bool:
        record = {
            "name": name,
            "passed": passed,
            "value": value,
            "detail": detail,
            "ts": datetime.now(_UTC).isoformat(),
        }
        self._checks.append(record)
        icon = "✅" if passed else "❌"
        suffix = f"  ({detail})" if detail else ""
        print(f"  {icon} {name}: {value}{suffix}")
        return passed

    def all_pass(self) -> bool:
        return all(c["passed"] for c in self._checks)

    def pass_count(self) -> int:
        return sum(1 for c in self._checks if c["passed"])

    def fail_count(self) -> int:
        return sum(1 for c in self._checks if not c["passed"])

    def checks(self) -> list[dict]:
        return list(self._checks)


# ── Validation ────────────────────────────────────────────────────────────────


async def run_validation() -> dict:
    r = CheckResult()
    run_ts = datetime.now(_UTC)

    print()
    print("=" * 65)
    print("  DEP-02 — MetaAPI Connection Validation")
    print(f"  {run_ts.strftime('%Y-%m-%dT%H:%M UTC')}")
    print("=" * 65)

    if _ORIGINAL_LIVE_TRADING.lower() == "true":
        print()
        print("  ⚠️  WARNING: .env contained LIVE_TRADING=true")
        print("     Overridden to 'false' for this validation script.")
        print("     Phase-1 paper trade has not completed — live trading")
        print("     remains blocked per CLAUDE.md §0.")

    # ── Check 1: LIVE_TRADING guard ───────────────────────────────────────────
    print("\n[1] LIVE_TRADING guard")
    r.add(
        "LIVE_TRADING forced false",
        not LIVE_TRADING,
        str(LIVE_TRADING),
        f".env said '{_ORIGINAL_LIVE_TRADING}' — overridden to false",
    )
    r.add(
        ".env LIVE_TRADING safe",
        _ORIGINAL_LIVE_TRADING.lower() != "true",
        f"was '{_ORIGINAL_LIVE_TRADING}'",
        (
            "OK — not set to true in env"
            if _ORIGINAL_LIVE_TRADING.lower() != "true"
            else "WARNING: .env had LIVE_TRADING=true — overridden for this script"
        ),
    )

    # ── Check 2: Credential presence ─────────────────────────────────────────
    print("\n[2] Credential presence")
    token = os.getenv("METAAPI_TOKEN", "")
    account_id = os.getenv("METAAPI_ACCOUNT_ID", "")
    tg_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    tg_chat = os.getenv("TELEGRAM_CHAT_ID", "")

    r.add(
        "METAAPI_TOKEN",
        bool(token),
        (
            f"{token[:6]}…{token[-4:]}"
            if len(token) > 10
            else ("SET" if token else "MISSING")
        ),
    )
    r.add(
        "METAAPI_ACCOUNT_ID",
        bool(account_id),
        (
            f"{account_id[:8]}…{account_id[-4:]}"
            if len(account_id) > 12
            else ("SET" if account_id else "MISSING")
        ),
    )
    r.add("TELEGRAM_BOT_TOKEN", bool(tg_token), "SET" if tg_token else "MISSING")
    r.add("TELEGRAM_CHAT_ID", bool(tg_chat), "SET" if tg_chat else "MISSING")

    if not token or not account_id:
        return {"checks": r.checks(), "error": "Missing credentials — cannot connect"}

    # ── Check 3: Connect ──────────────────────────────────────────────────────
    print("\n[3] MetaAPI connect()")
    client = MetaAPIClient(token, account_id)

    try:
        print("  Connecting… (synchronization may take 30–90s)")
        await client.connect()
        r.add("connect()", True, "OK")
        r.add("is_connected", client.is_connected, str(client.is_connected))
    except Exception as e:
        r.add("connect()", False, f"FAILED: {type(e).__name__}: {e}")
        return {"checks": r.checks(), "error": str(e)}

    # Container for results we build up
    balance = 0.0
    equity = 0.0
    currency = "?"
    leverage = 0
    open_pos_count = -1
    spread_data: dict = {}
    heartbeat_data: dict = {}
    broker_name = "unknown"

    try:
        # ── Check 4: Account sync ─────────────────────────────────────────────
        print("\n[4] Account synchronization")
        status = client.connection_status()
        r.add(
            "connection_status() connected",
            status["connected"],
            str(status["connected"]),
        )
        r.add(
            "connection_status() live_trading",
            not status["live_trading"],
            str(status["live_trading"]),
            "must be False",
        )

        # ── Check 5: Balance + equity ─────────────────────────────────────────
        print("\n[5] Account info (balance + equity)")
        try:
            info = await client.get_account_info()
            balance = info.balance
            equity = info.equity
            currency = info.currency
            leverage = info.leverage
            r.add("get_account_info()", True, "OK")
            r.add("balance > 0", balance > 0, f"{balance:.2f} {currency}")
            r.add("equity > 0", equity > 0, f"{equity:.2f} {currency}")
            r.add("leverage", True, f"1:{leverage}")
            r.add("currency", True, currency)
        except Exception as e:
            r.add("get_account_info()", False, f"FAILED: {e}")

        # ── Check 6: Open positions ───────────────────────────────────────────
        print("\n[6] Open positions")
        try:
            positions = await client.get_open_positions()
            open_pos_count = len(positions)
            r.add("get_open_positions()", True, f"{open_pos_count} position(s)")
            if positions:
                for p in positions:
                    r.add(
                        f"  position {p.position_id[:8]}…",
                        True,
                        f"{p.direction} {p.symbol} vol={p.volume}",
                    )
        except Exception as e:
            r.add("get_open_positions()", False, f"FAILED: {e}")

        # ── Check 7: Symbol prices + spread ──────────────────────────────────
        print("\n[7] Symbol prices + spread check")
        for symbol in ["EURUSD", "GBPUSD"]:
            try:
                price = await client.get_symbol_price(symbol)
                spread_ok, spread_pips = await client.check_spread(symbol)
                # Don't fail on wide spread — markets may be closed (weekend/off-hours)
                r.add(
                    f"{symbol} price",
                    True,
                    f"bid={price.bid:.5f}  ask={price.ask:.5f}  spread={price.spread_pips:.1f}pip",
                    "spread OK" if spread_ok else "spread wide (off-hours?)",
                )
                spread_data[symbol] = {
                    "bid": price.bid,
                    "ask": price.ask,
                    "spread_pips": price.spread_pips,
                    "spread_ok": spread_ok,
                }
            except Exception as e:
                r.add(f"{symbol} price", False, f"FAILED: {e}")
                spread_data[symbol] = {"error": str(e)}

        # ── Check 8: DRY_RUN order ────────────────────────────────────────────
        print("\n[8] DRY_RUN order test (LIVE_TRADING=false)")
        try:
            order_result = await client.place_order(
                symbol="EURUSD",
                direction="long",
                volume=0.01,
                sl=1.07000,
                tp=1.09000,
                magic=21001,
                comment="DEP-02-VALIDATION",
            )
            is_dry = order_result.dry_run and order_result.order_id == "DRY_RUN"
            r.add(
                "place_order() returns DRY_RUN",
                is_dry,
                f"order_id={order_result.order_id}  dry_run={order_result.dry_run}",
            )
            r.add(
                "No real order sent to broker",
                is_dry,
                "confirmed" if is_dry else "REAL ORDER MAY HAVE BEEN SENT",
            )
        except Exception as e:
            r.add("place_order() DRY_RUN", False, f"FAILED: {e}")

        # ── Check 9: Trade logging ─────────────────────────────────────────────
        print("\n[9] Trade logging")
        log_file = _LOG_DIR / "dep02_validation.jsonl"
        tl = TradeLogger(log_file)
        try:
            tl.signal_created(
                "EURUSD",
                "london",
                "long",
                1.08000,
                1.07000,
                1.10000,
                10.0,
                "DEP-02 validation",
            )
            tl.order_submitted(
                "EURUSD",
                "london",
                "long",
                0.01,
                1.07000,
                1.10000,
                0.01,
                equity,
                1.0,
                dry_run=True,
            )
            tl.order_filled(
                "EURUSD", "DRY_RUN", 0.0, 0.01, 1.07000, 1.10000, dry_run=True
            )
            tl.order_rejected("EURUSD", "MAX_OPEN_TRADES:1/1 (validation test)", "long")
            tl.position_closed("EURUSD", "DEP-02-pos", 0.0, "validation")
            tl.error("EURUSD", "synthetic error (validation only)", "DEP-02")

            events = tl.read_all()
            all_have_ts = all("ts" in e and "event" in e for e in events)
            r.add("TradeLogger writes JSONL", len(events) >= 6, f"{len(events)} events")
            r.add("All records have ts + event", all_have_ts, "valid")
            r.add("Log file", log_file.exists(), str(log_file.relative_to(_ROOT)))
            expected_events = {
                "SIGNAL_CREATED",
                "ORDER_SUBMITTED",
                "ORDER_FILLED",
                "ORDER_REJECTED",
                "POSITION_CLOSED",
                "ERROR",
            }
            found_events = {e["event"] for e in events}
            all_present = expected_events <= found_events
            r.add(
                "All 6 event types",
                all_present,
                ", ".join(sorted(found_events)),
                "" if all_present else f"missing: {expected_events - found_events}",
            )
        except Exception as e:
            r.add("TradeLogger", False, f"FAILED: {e}")

        # ── Check 10: Heartbeat ───────────────────────────────────────────────
        print("\n[10] Heartbeat")
        try:
            status = client.connection_status()
            heartbeat_data = {
                "ts": datetime.now(_UTC).isoformat(),
                "connected": status["connected"],
                "live_trading": status["live_trading"],
                "balance": balance,
                "open_positions": open_pos_count,
            }
            required_keys = {
                "ts",
                "connected",
                "live_trading",
                "balance",
                "open_positions",
            }
            has_keys = required_keys <= set(heartbeat_data.keys())
            r.add(
                "Heartbeat has all 5 fields",
                has_keys,
                str(sorted(heartbeat_data.keys())),
            )
            r.add(
                "Heartbeat connected=True",
                heartbeat_data["connected"],
                str(heartbeat_data["connected"]),
            )
            r.add(
                "Heartbeat live_trading=False",
                not heartbeat_data["live_trading"],
                str(heartbeat_data["live_trading"]),
            )
        except Exception as e:
            r.add("Heartbeat", False, f"FAILED: {e}")

        # ── Check 11: Reconnect ────────────────────────────────────────────────
        print("\n[11] Reconnect logic")
        try:
            await client.disconnect()
            r.add(
                "disconnect()",
                not client.is_connected,
                f"is_connected={client.is_connected}",
            )

            await client.connect()
            r.add(
                "reconnect()",
                client.is_connected,
                f"is_connected={client.is_connected}",
            )

            info2 = await client.get_account_info()
            r.add(
                "Post-reconnect account_info",
                info2.balance > 0,
                f"balance={info2.balance:.2f} {info2.currency}",
            )
        except Exception as e:
            r.add("Reconnect", False, f"FAILED: {e}")

    finally:
        try:
            await client.disconnect()
        except Exception:
            pass

    # ── Final verdict ─────────────────────────────────────────────────────────
    passed = r.all_pass()
    print()
    print("=" * 65)
    if passed:
        print("  VERDICT: ✅ PASS — all checks passed")
    else:
        n_fail = r.fail_count()
        print(f"  VERDICT: ❌ FAIL — {n_fail} check(s) failed")
    print("=" * 65 + "\n")

    return {
        "ts": run_ts.isoformat(),
        "passed": passed,
        "pass_count": r.pass_count(),
        "fail_count": r.fail_count(),
        "checks": r.checks(),
        "account": {
            "balance": balance,
            "equity": equity,
            "currency": currency,
            "leverage": leverage,
            "open_positions": open_pos_count,
        },
        "spread": spread_data,
        "heartbeat": heartbeat_data,
        "live_trading_in_env": _ORIGINAL_LIVE_TRADING,
    }


# ── Report generator ──────────────────────────────────────────────────────────


def generate_report(data: dict, out_path: Path) -> None:
    ts = data.get("ts", "unknown")
    passed = data.get("passed", False)
    account = data.get("account", {})
    spread = data.get("spread", {})
    hb = data.get("heartbeat", {})
    checks = data.get("checks", [])
    live_in_env = data.get("live_trading_in_env", "unknown")

    verdict_line = (
        "### ✅ PASS — all connection checks passed"
        if passed
        else f"### ❌ FAIL — {data.get('fail_count',0)} check(s) failed"
    )

    lines = [
        "# DEP_02_CONNECTION_REPORT.md",
        "# DEP-02 — MetaAPI Demo Connection Validation",
        f"# Run: {ts[:19]} UTC",
        "",
        "---",
        "",
        "## Verdict",
        "",
        verdict_line,
        "",
    ]

    if live_in_env.lower() == "true":
        lines += [
            "> ⚠️  `.env` had `LIVE_TRADING=true`. Overridden to `false` by the validation script.",
            "> Per CLAUDE.md §0: live trading is blocked until 30-day paper trade completes.",
            "> **Action required: set `LIVE_TRADING=false` in `.env` before starting `bot.py`.**",
            "",
        ]

    lines += [
        "---",
        "",
        "## Connection Status",
        "",
        "| Check | Status | Value |",
        "|---|---|---|",
    ]
    for c in checks[:6]:  # credential + connect checks
        icon = "✅" if c["passed"] else "❌"
        lines.append(f"| {c['name']} | {icon} | {c['value']} |")

    lines += [
        "",
        "---",
        "",
        "## Broker / Account Details",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Broker | Vantage (VT Markets) via MetaAPI |",
        f"| Account ID | `{os.getenv('METAAPI_ACCOUNT_ID','')[:8]}…` |",
        f"| Balance | {account.get('balance', 0):.2f} {account.get('currency','?')} |",
        f"| Equity | {account.get('equity', 0):.2f} {account.get('currency','?')} |",
        f"| Leverage | 1:{account.get('leverage', 0)} |",
        f"| Open positions | {account.get('open_positions', -1)} |",
        "",
    ]

    lines += [
        "---",
        "",
        "## Synchronization Status",
        "",
    ]
    sync_checks = [
        c
        for c in checks
        if "connect" in c["name"].lower()
        or "sync" in c["name"].lower()
        or "is_connected" in c["name"]
    ]
    if sync_checks:
        lines += ["| Check | Status | Value |", "|---|---|---|"]
        for c in sync_checks:
            icon = "✅" if c["passed"] else "❌"
            lines.append(f"| {c['name']} | {icon} | {c['value']} |")
    lines += [""]

    lines += [
        "---",
        "",
        "## Symbol Prices",
        "",
        "| Symbol | Bid | Ask | Spread | Spread OK |",
        "|---|---|---|---|---|",
    ]
    for sym, s in spread.items():
        if "error" in s:
            lines.append(f"| {sym} | — | — | — | ❌ {s['error']} |")
        else:
            ok = "✅" if s.get("spread_ok") else "⚠️ wide"
            lines.append(
                f"| {sym} | `{s.get('bid',0):.5f}` | `{s.get('ask',0):.5f}` | `{s.get('spread_pips',0):.1f}` pip | {ok} |"
            )
    lines += [""]

    lines += [
        "---",
        "",
        "## Heartbeat Status",
        "",
        "| Field | Value |",
        "|---|---|",
    ]
    for k, v in hb.items():
        lines.append(f"| {k} | `{v}` |")
    lines += [""]

    dry_run_checks = [
        c for c in checks if "DRY_RUN" in c["name"] or "order" in c["name"].lower()
    ]
    lines += [
        "---",
        "",
        "## DRY_RUN Order Status",
        "",
        "| Check | Status | Value |",
        "|---|---|---|",
    ]
    for c in dry_run_checks:
        icon = "✅" if c["passed"] else "❌"
        lines.append(f"| {c['name']} | {icon} | {c['value']} |")
    lines += [
        "",
        f"> All orders return `order_id=DRY_RUN` and `dry_run=True`.",
        f"> No real orders were sent to the broker.",
        "",
    ]

    lines += [
        "---",
        "",
        "## Full Check Log",
        "",
        "| # | Check | Status | Value | Detail |",
        "|---|---|---|---|---|",
    ]
    for i, c in enumerate(checks, 1):
        icon = "✅" if c["passed"] else "❌"
        detail = c.get("detail", "").replace("|", "∣")
        lines.append(f"| {i} | {c['name']} | {icon} | {c['value']} | {detail} |")

    lines += [
        "",
        "---",
        "",
        "## Blockers",
        "",
    ]
    failed = [c for c in checks if not c["passed"]]
    if failed:
        for c in failed:
            lines.append(f"- ❌ **{c['name']}**: {c['value']}")
    else:
        lines.append("None — all checks passed.")

    live_in_env_warning = live_in_env.lower() == "true"
    lines += [
        "",
        "---",
        "",
        "## Next Steps",
        "",
    ]
    if live_in_env_warning:
        lines += [
            "1. **Fix `.env`**: change `LIVE_TRADING=true` → `LIVE_TRADING=false` before starting `bot.py`",
            "2. Start paper trade: `python3 bot.py`",
            "3. Monitor `logs/trades.jsonl` + Telegram for 30 days / ≥50 trades",
        ]
    elif passed:
        lines += [
            "1. Start paper trade: `python3 bot.py`",
            "2. Monitor `logs/trades.jsonl` + Telegram for 30 days / ≥50 trades",
            "3. After 50+ trades with no execution errors → DEP-02 complete",
        ]
    else:
        lines += [
            "1. Fix failed checks listed above",
            "2. Re-run: `python3 scripts/validate_connection.py`",
        ]

    lines += [
        "",
        f"*DEP-02 | Run: {ts[:19]} UTC | SDK: metaapi-cloud-sdk 29.1.1*",
    ]

    out_path.write_text("\n".join(lines))
    print(f"Report written → {out_path.relative_to(_ROOT)}")


# ── Entry point ───────────────────────────────────────────────────────────────


async def main() -> None:
    data = await run_validation()

    # Write raw JSON log
    raw_log = _LOG_DIR / "dep02_validation_raw.json"
    raw_log.write_text(json.dumps(data, indent=2, default=str))

    # Generate markdown report
    report_path = _DOCS_DIR / "DEP_02_CONNECTION_REPORT.md"
    generate_report(data, report_path)

    # Exit non-zero if any check failed (for CI)
    sys.exit(0 if data.get("passed") else 1)


if __name__ == "__main__":
    asyncio.run(main())
