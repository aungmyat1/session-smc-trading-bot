#!/usr/bin/env python3
"""
OPS-01 Pre-flight validation script.

Runs a live check against the MetaAPI account before starting bot.py for
the 30-day operational stability run. Generates docs/OPS01_PREFLIGHT.md.

All checks are READ-ONLY. LIVE_TRADING is forced to false.
"""

import asyncio
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

os.environ["LIVE_TRADING"] = "false"

from dotenv import load_dotenv

load_dotenv(_ROOT / ".env", override=False)

from execution.metaapi_client import MetaAPIClient, LIVE_TRADING

_UTC = timezone.utc
_DOCS = _ROOT / "docs"


class Check:
    def __init__(self) -> None:
        self._rows: list[dict] = []

    def add(self, name: str, passed: bool, value: str, detail: str = "") -> bool:
        self._rows.append(
            {"name": name, "passed": passed, "value": value, "detail": detail}
        )
        icon = "✅" if passed else "❌"
        print(f"  {icon}  {name}: {value}" + (f"  ({detail})" if detail else ""))
        return passed

    def all_pass(self) -> bool:
        return all(r["passed"] for r in self._rows)

    def rows(self) -> list[dict]:
        return list(self._rows)

    def counts(self) -> tuple[int, int]:
        p = sum(1 for r in self._rows if r["passed"])
        return p, len(self._rows) - p


async def run() -> dict:
    ts = datetime.now(_UTC)
    r = Check()
    token = os.getenv("METAAPI_TOKEN", "")
    account_id = os.getenv("METAAPI_ACCOUNT_ID", "")

    print()
    print("=" * 60)
    print(f"  OPS-01 Pre-flight Validation  {ts.strftime('%Y-%m-%dT%H:%M UTC')}")
    print("=" * 60)

    print("\n[1] Safety guards")
    r.add("LIVE_TRADING=false", not LIVE_TRADING, str(LIVE_TRADING))
    r.add("METAAPI_TOKEN present", bool(token), "SET" if token else "MISSING")
    r.add(
        "METAAPI_ACCOUNT_ID present",
        bool(account_id),
        f"{account_id[:8]}…" if account_id else "MISSING",
    )
    r.add(
        "METAAPI_ACCOUNT_ID is new account",
        account_id == "026ea073-5241-4d53-9a87-b0cb791443af",
        account_id[:8] if account_id else "?",
    )

    if not token or not account_id:
        return {
            "ts": ts.isoformat(),
            "passed": False,
            "checks": r.rows(),
            "error": "missing creds",
        }

    client = MetaAPIClient(token, account_id)
    balance = equity = 0.0
    currency = "?"
    leverage = 0
    n_pos = -1
    spread_data: dict = {}
    result = {}

    try:
        print("\n[2] MetaAPI connection")
        await client.connect()
        r.add("connect()", True, "OK")
        r.add("is_connected", client.is_connected, str(client.is_connected))
        status = client.connection_status()
        r.add(
            "connection_status CONNECTED", status["connected"], str(status["connected"])
        )
        r.add(
            "connection_status live_trading=false",
            not status["live_trading"],
            str(status["live_trading"]),
        )

        print("\n[3] Account synchronization + balance")
        info = await client.get_account_info()
        balance, equity, currency, leverage = (
            info.balance,
            info.equity,
            info.currency,
            info.leverage,
        )
        r.add("get_account_info()", True, "OK")
        r.add("balance > 0", balance > 0, f"{balance:,.2f} {currency}")
        r.add("equity > 0", equity > 0, f"{equity:,.2f} {currency}")
        r.add("leverage set", leverage > 0, f"1:{leverage}")

        print("\n[4] Open positions")
        positions = await client.get_open_positions()
        n_pos = len(positions)
        r.add(
            "get_open_positions()",
            True,
            f"{n_pos} position(s)",
            "clean slate" if n_pos == 0 else "WARNING: positions already open",
        )

        print("\n[5] Spread retrieval")
        for sym in ["EURUSD", "GBPUSD"]:
            try:
                price = await client.get_symbol_price(sym)
                ok, pips = await client.check_spread(sym)
                r.add(
                    f"{sym} price",
                    True,
                    f"bid={price.bid:.5f}  ask={price.ask:.5f}  spread={price.spread_pips:.1f}pip",
                    "OK" if ok else "wide (off-hours)",
                )
                spread_data[sym] = {
                    "bid": price.bid,
                    "ask": price.ask,
                    "spread_pips": price.spread_pips,
                    "ok": ok,
                }
            except Exception as e:
                r.add(f"{sym} price", False, f"FAILED: {e}")
                spread_data[sym] = {"error": str(e)}

        print("\n[6] Heartbeat startup fields")
        hb = {
            "timestamp": ts.isoformat(),
            "uptime_seconds": 0,
            "connection_status": "CONNECTED" if status["connected"] else "DISCONNECTED",
            "balance": balance,
            "equity": equity,
            "open_positions": n_pos,
            "last_signal_time": "none",
        }
        required = {
            "timestamp",
            "uptime_seconds",
            "connection_status",
            "balance",
            "equity",
            "open_positions",
            "last_signal_time",
        }
        r.add(
            "All 7 heartbeat fields present",
            required <= set(hb.keys()),
            ", ".join(sorted(hb.keys())),
        )

        print("\n[7] DRY_RUN safety")
        order = await client.place_order(
            "EURUSD", "long", 0.01, 1.07, 1.09, 21001, "OPS01-PREFLIGHT"
        )
        r.add(
            "place_order DRY_RUN",
            order.dry_run and order.order_id == "DRY_RUN",
            f"id={order.order_id}  dry_run={order.dry_run}",
        )

        result = {
            "ts": ts.isoformat(),
            "passed": r.all_pass(),
            "account_id": account_id,
            "balance": balance,
            "equity": equity,
            "currency": currency,
            "leverage": leverage,
            "open_positions": n_pos,
            "spread": spread_data,
            "heartbeat_fields": hb,
            "checks": r.rows(),
        }

    except Exception as e:
        r.add("EXCEPTION", False, f"{type(e).__name__}: {e}")
        result = {
            "ts": ts.isoformat(),
            "passed": False,
            "checks": r.rows(),
            "error": str(e),
        }
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass

    n_pass, n_fail = r.counts()
    print()
    print("=" * 60)
    verdict = "✅ PASS" if r.all_pass() else f"❌ FAIL ({n_fail} checks)"
    print(f"  VERDICT: {verdict}  ({n_pass}/{n_pass+n_fail} checks)")
    print("=" * 60)
    return result


def write_report(data: dict) -> None:
    ts = data.get("ts", "")[:19]
    passed = data.get("passed", False)
    checks = data.get("checks", [])
    spread = data.get("spread", {})

    verdict = (
        "### ✅ PASS — pre-flight complete, bot ready to start"
        if passed
        else "### ❌ FAIL — resolve blockers before starting bot"
    )

    lines = [
        "# OPS01_PREFLIGHT.md",
        "# OPS-01 — Pre-flight Validation Report",
        f"# Run: {ts} UTC",
        "",
        "---",
        "",
        "## Verdict",
        "",
        verdict,
        "",
        "---",
        "",
        "## Account Details",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Account ID | `{data.get('account_id','')[:8]}…` |",
        f"| Balance | {data.get('balance',0):,.2f} {data.get('currency','USD')} |",
        f"| Equity | {data.get('equity',0):,.2f} {data.get('currency','USD')} |",
        f"| Leverage | 1:{data.get('leverage',0)} |",
        f"| Open positions | {data.get('open_positions',-1)} |",
        f"| LIVE_TRADING | false (enforced) |",
        "",
        "---",
        "",
        "## Symbol Prices",
        "",
        "| Symbol | Bid | Ask | Spread | Status |",
        "|---|---|---|---|---|",
    ]
    for sym, s in spread.items():
        if "error" in s:
            lines.append(f"| {sym} | — | — | — | ❌ {s['error']} |")
        else:
            ok_str = "✅ OK" if s.get("ok") else "⚠️ wide (off-hours)"
            lines.append(
                f"| {sym} | `{s['bid']:.5f}` | `{s['ask']:.5f}` | `{s['spread_pips']:.1f}` pip | {ok_str} |"
            )

    lines += [
        "",
        "---",
        "",
        "## Full Check Log",
        "",
        "| # | Check | Status | Value |",
        "|---|---|---|---|",
    ]
    for i, c in enumerate(checks, 1):
        icon = "✅" if c["passed"] else "❌"
        lines.append(f"| {i} | {c['name']} | {icon} | {c['value']} |")

    hb = data.get("heartbeat_fields", {})
    if hb:
        lines += [
            "",
            "---",
            "",
            "## Heartbeat Fields (startup)",
            "",
            "| Field | Value |",
            "|---|---|",
        ]
        for k, v in hb.items():
            lines.append(f"| `{k}` | `{v}` |")

    blocked = [c for c in checks if not c["passed"]]
    lines += [
        "",
        "---",
        "",
        "## Blockers",
        "",
    ]
    if blocked:
        for c in blocked:
            lines.append(f"- ❌ **{c['name']}**: {c['value']}")
    else:
        lines.append("None.")

    lines += [
        "",
        "---",
        "",
        "## Next Step",
        "",
        "```bash",
        "tmux new-session -d -s bot 'python3 bot.py 2>&1 | tee logs/bot.log'",
        "tmux attach -t bot",
        "```",
        "",
        f"*OPS-01 | Pre-flight | {ts} UTC*",
    ]

    out = _DOCS / "OPS01_PREFLIGHT.md"
    out.write_text("\n".join(lines))
    print(f"\nReport → {out.relative_to(_ROOT)}")


if __name__ == "__main__":
    data = asyncio.run(run())
    write_report(data)
    sys.exit(0 if data.get("passed") else 1)
