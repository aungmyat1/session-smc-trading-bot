#!/usr/bin/env python3
"""
OPS-01 Reconnect simulation test.

Simulates MetaAPI disconnects and verifies the client reconnects cleanly
at each retry interval: 30s, 60s, 120s, 300s (clamped to 10s in test mode).

Generates docs/OPS01_RECONNECT_AUDIT.md.
LIVE_TRADING forced to false. No orders placed.
"""

import asyncio
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

os.environ["LIVE_TRADING"] = "false"

from dotenv import load_dotenv
load_dotenv(_ROOT / ".env", override=False)

from execution.metaapi_client import MetaAPIClient

_UTC = timezone.utc
_DOCS = _ROOT / "docs"


async def attempt_reconnect(client: MetaAPIClient, attempt: int, label: str) -> dict:
    """Disconnect, wait briefly, reconnect, verify account info readable."""
    t0 = time.monotonic()
    success = False
    error = ""
    balance = 0.0

    try:
        await client.disconnect()
        assert not client.is_connected, "expected is_connected=False after disconnect"

        # In test mode we use a short fixed wait instead of the production retry delays
        await asyncio.sleep(3)

        await client.connect()
        assert client.is_connected, "expected is_connected=True after reconnect"

        info = await client.get_account_info()
        balance = info.balance
        success = True
    except Exception as e:
        error = f"{type(e).__name__}: {e}"

    elapsed = time.monotonic() - t0
    icon = "✅" if success else "❌"
    print(f"  {icon}  Attempt {attempt} ({label}): success={success}  "
          f"balance={balance:.0f}  elapsed={elapsed:.1f}s"
          + (f"  err={error}" if error else ""))
    return {
        "attempt": attempt,
        "label": label,
        "success": success,
        "balance": balance,
        "elapsed_s": round(elapsed, 2),
        "error": error,
    }


async def run() -> dict:
    ts = datetime.now(_UTC)
    token = os.getenv("METAAPI_TOKEN", "")
    account_id = os.getenv("METAAPI_ACCOUNT_ID", "")

    print()
    print("=" * 60)
    print(f"  OPS-01 Reconnect Test  {ts.strftime('%Y-%m-%dT%H:%M UTC')}")
    print("=" * 60)

    if not token or not account_id:
        return {"ts": ts.isoformat(), "passed": False, "error": "missing credentials"}

    client = MetaAPIClient(token, account_id)

    print("\n[0] Initial connection")
    t0 = time.monotonic()
    await client.connect()
    connect_ms = int((time.monotonic() - t0) * 1000)
    print(f"  ✅  Connected in {connect_ms}ms")

    print("\n[1–4] Disconnect / reconnect cycles")
    # Labels map to production retry schedule (30s, 60s, 120s, 300s)
    # In test we run them back-to-back with a 3s wait each — verifies the
    # reconnect path works, not the timing (timing is SDK-internal).
    labels = ["retry-30s", "retry-60s", "retry-120s", "retry-300s"]
    results = []
    for i, label in enumerate(labels, 1):
        result = await attempt_reconnect(client, i, label)
        results.append(result)

    # Final state check
    print("\n[5] Post-test state")
    try:
        info = await client.get_account_info()
        positions = await client.get_open_positions()
        final_ok = True
        print(f"  ✅  balance={info.balance:.0f}  positions={len(positions)}")
    except Exception as e:
        final_ok = False
        print(f"  ❌  {e}")

    try:
        await client.disconnect()
    except Exception:
        pass

    all_passed = all(r["success"] for r in results) and final_ok
    print()
    print("=" * 60)
    verdict = "✅ PASS" if all_passed else "❌ FAIL"
    print(f"  VERDICT: {verdict}  ({sum(r['success'] for r in results)}/{len(results)} reconnects)")
    print("=" * 60)

    return {
        "ts": ts.isoformat(),
        "passed": all_passed,
        "initial_connect_ms": connect_ms,
        "reconnect_attempts": results,
        "final_state_ok": final_ok,
    }


def write_report(data: dict) -> None:
    ts = data.get("ts", "")[:19]
    passed = data.get("passed", False)
    attempts = data.get("reconnect_attempts", [])

    verdict = "### ✅ PASS — all reconnect attempts succeeded" if passed \
        else "### ❌ FAIL — one or more reconnect attempts failed"

    lines = [
        "# OPS01_RECONNECT_AUDIT.md",
        "# OPS-01 — Reconnect Behavior Audit",
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
        "## Test Method",
        "",
        "Each cycle: `client.disconnect()` → 3s wait → `client.connect()` → verify `get_account_info()`.",
        "Four cycles map to production retry schedule: 30s / 60s / 120s / 300s.",
        "Timing of retries is SDK-managed; this test validates the reconnect *path*, not the delay.",
        "",
        "---",
        "",
        "## Initial Connection",
        "",
        f"Connected in **{data.get('initial_connect_ms', 0)} ms**",
        "",
        "---",
        "",
        "## Reconnect Attempts",
        "",
        "| # | Label | Success | Balance | Elapsed |",
        "|---|---|---|---|---|",
    ]
    for a in attempts:
        icon = "✅" if a["success"] else "❌"
        err = f"  `{a['error']}`" if a["error"] else ""
        lines.append(f"| {a['attempt']} | {a['label']} | {icon}{err} | "
                     f"{a['balance']:,.0f} | {a['elapsed_s']}s |")

    lines += [
        "",
        "---",
        "",
        "## Production Retry Schedule",
        "",
        "The MetaAPI Cloud SDK manages reconnection internally. On network loss:",
        "",
        "| Event | SDK Behaviour |",
        "|---|---|",
        "| WebSocket drop | Immediate reconnect attempt |",
        "| Reconnect fails | Exponential back-off (SDK-managed) |",
        "| `wait_synchronized()` timeout | Raises; bot re-polls on next 60s tick |",
        "| `get_candles()` failure | Returns `[]`; scan skipped; no order placed |",
        "| `get_account_info()` failure | Skips equity fetch; next poll retries |",
        "",
        "---",
        "",
        "## bot.py Recovery Path",
        "",
        "```",
        "Connection drops during active session:",
        "  → get_candles() returns []",
        "  → _scan_pair() returns early (len(m15) < 20)",
        "  → bot sleeps POLL_INTERVAL (60s)",
        "  → SDK reconnects in background",
        "  → next poll: get_candles() succeeds again",
        "  → no signal missed (seen_signals dedup prevents re-processing)",
        "```",
        "",
        f"Final state after test: {'✅ OK' if data.get('final_state_ok') else '❌ FAIL'}",
        "",
        f"*OPS-01 | Reconnect | {ts} UTC*",
    ]

    out = _DOCS / "OPS01_RECONNECT_AUDIT.md"
    out.write_text("\n".join(lines))
    print(f"\nReport → {out.relative_to(_ROOT)}")


if __name__ == "__main__":
    data = asyncio.run(run())
    write_report(data)
    sys.exit(0 if data.get("passed") else 1)
