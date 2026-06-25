#!/usr/bin/env python3
"""
capture_spreads.py — measure REAL Vantage spreads at the killzone hours.

Why: the backtests assume a fixed round-trip cost (inherited from VT Markets).
At ST-A2's PF_2x=1.025 the verdict is decided by that number. Forex spreads
widen at session opens — exactly when this strategy trades — so the headline
spread understates the true cost. This logs the live spread each poll, tags it
london / new_york / off, and reports the killzone-hour average so you can
fill config/costs.json with numbers that mean something for your account.

Reads market data only. Places NO orders. Reuses the bot's MetaApiClient.

Usage:
    export METAAPI_TOKEN=...  METAAPI_ACCOUNT_ID=...
    python3 scripts/capture_spreads.py --commission-pips 0.0 --interval 30
    # leave running across several London and NY sessions.

--commission-pips : per-side-folded round-trip commission in pips to ADD to the
                    measured spread (Vantage Raw ~0.6; Standard 0.0 — commission
                    is embedded in the spread). Default 0.0.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import logging
import os
import signal
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_ROOT / ".env")
sys.path.insert(0, str(_ROOT))

from execution.metaapi_client import MetaAPIClient          # noqa: E402
from strategy.session_liquidity.session_builder import (    # noqa: E402
    classify_session as _classify_session_builder,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD"]

OUT = _ROOT / "research" / "spread_samples.csv"

_UTC = timezone.utc

# Pip size per symbol: used to recompute spread from raw bid/ask.
# MetaApiClient.get_symbol_price() hardcodes ÷0.0001, so USDJPY's
# spread_pips field is 100× too large — we recompute here.
PIP_SIZE: dict[str, float] = {
    "EURUSD": 0.0001,
    "GBPUSD": 0.0001,
    "USDJPY": 0.01,
    "AUDUSD": 0.0001,
}

CSV_HEADER = ["time_utc", "symbol", "session", "hour", "minute", "spread_pips"]


# ── Pure functions (testable without MetaAPI) ─────────────────────────────────

def session_label(dt_utc: datetime) -> str:
    """
    DST-aware session classification — wraps session_builder.classify_session().

    Returns 'london' | 'new_york' | 'off'.
    Uses EST/EDT (America/New_York) so killzone hours shift with daylight saving.

    London:   EST 02:00–04:59 → UTC 07–10 (winter) or 06–09 (summer).
    New York: EST 07:00–09:59 → UTC 12–15 (winter) or 11–14 (summer).

    The fixed UTC windows in the original script (07-10 / 13-16) are wrong in
    summer when EDT shifts London to 06-09 UTC and NY to 11-14 UTC.
    """
    result = _classify_session_builder(dt_utc)
    return result if result is not None else "off"


def spread_pips(bid: float, ask: float, symbol: str) -> float:
    """
    Compute spread in pips from raw bid/ask using the correct pip size.

    MetaApiClient.get_symbol_price() always divides by 0.0001 (5-decimal pairs).
    For USDJPY (2-decimal pair, pip=0.01), that gives a value 100× too large.
    This function uses PIP_SIZE to recompute correctly.
    """
    pip = PIP_SIZE.get(symbol, 0.0001)
    return round((ask - bid) / pip, 2)


def csv_row(now: datetime, sym: str, sess: str, sp: float) -> list:
    """Build a single CSV data row."""
    return [
        now.isoformat(),
        sym,
        sess,
        now.hour,
        now.minute,
        round(sp, 3),
    ]


def update_agg(
    agg: "dict[tuple[str, str], list]",
    sym: str,
    sess: str,
    sp: float,
) -> None:
    """Accumulate spread into aggregation dict: (sym, sess) → [sum, count]."""
    agg[(sym, sess)][0] += sp
    agg[(sym, sess)][1] += 1


def build_summary(
    agg: "dict[tuple[str, str], list]",
    commission_pips: float,
    pairs: "list[str]",
) -> list[str]:
    """
    Produce human-readable summary lines for killzone sessions.

    Returns a list of strings to print / log. Empty list if no killzone samples.
    """
    lines: list[str] = []
    for sym in pairs:
        samples = [
            (sess, agg[(sym, sess)])
            for sess in ("london", "new_york")
            if agg[(sym, sess)][1] > 0
        ]
        if not samples:
            lines.append(
                f"  {sym}: no killzone samples yet "
                "(run across a London or NY session window)."
            )
            continue
        tot_sum = sum(s[1][0] for s in samples)
        tot_n = sum(s[1][1] for s in samples)
        avg_spread = tot_sum / tot_n
        std_cost = avg_spread + commission_pips
        per_sess = " | ".join(
            f"{sess}={agg[(sym, sess)][0] / agg[(sym, sess)][1]:.2f}p"
            f"(n={agg[(sym, sess)][1]})"
            for sess, _ in samples
        )
        lines.append(
            f"  {sym}: killzone avg {avg_spread:.2f}p + {commission_pips:.2f} comm"
            f' => "standard": {std_cost:.2f}, "stress2x": {std_cost * 2:.2f}'
            f"  [{per_sess}]"
        )
    return lines


# ── Reconnect helper ──────────────────────────────────────────────────────────

async def reconnect_if_needed(client: MetaAPIClient, label: str) -> bool:
    """
    If client is not connected, attempt one reconnect.

    Returns True if the client is (or becomes) connected; False otherwise.
    Does not raise. Compatible with BUG-01's _rpc() 30-second timeout.
    """
    if client.is_connected:
        return True
    logger.warning("%s: connection lost — attempting reconnect", label)
    try:
        ok = await client.reconnect()
        if ok:
            logger.info("%s: reconnected successfully", label)
        else:
            logger.error("%s: reconnect failed", label)
        return ok
    except Exception as exc:  # noqa: BLE001
        logger.error("%s: reconnect raised %s", label, exc)
        return False


# ── Main ──────────────────────────────────────────────────────────────────────

async def main() -> None:
    ap = argparse.ArgumentParser(description="Capture live Vantage spreads at killzone hours.")
    ap.add_argument(
        "--commission-pips", type=float, default=0.0,
        help="Round-trip commission in pips to add to spread (Vantage Raw ~0.6; Standard 0.0).",
    )
    ap.add_argument(
        "--interval", type=int, default=30,
        help="Seconds between samples (default 30).",
    )
    ap.add_argument(
        "--pairs", nargs="+", default=PAIRS,
        help="Symbols to sample (default: EURUSD GBPUSD USDJPY AUDUSD).",
    )
    args = ap.parse_args()
    pairs: list[str] = args.pairs

    token = os.getenv("METAAPI_TOKEN")
    acct = os.getenv("METAAPI_ACCOUNT_ID")
    if not token or not acct:
        print("ERROR: Set METAAPI_TOKEN and METAAPI_ACCOUNT_ID before running.")
        sys.exit(2)

    # ── Asyncio-compatible stop event ─────────────────────────────────────────
    stop_event = asyncio.Event()

    def _on_stop() -> None:
        logger.info("Stop signal received — finishing current poll then reporting.")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _on_stop)
        except NotImplementedError:
            # Windows — fall back to threading signal
            signal.signal(sig, lambda *_: stop_event.set())

    # ── Connection ────────────────────────────────────────────────────────────
    client = MetaAPIClient(token, acct)
    print("Connecting to Vantage via MetaAPI…")
    await client.connect()
    print(
        f"Connected. Sampling {pairs} every {args.interval}s. "
        "Ctrl-C to stop and print report.\n"
    )

    new_file = not OUT.exists() or OUT.stat().st_size == 0
    OUT.parent.mkdir(parents=True, exist_ok=True)

    agg: dict[tuple[str, str], list] = defaultdict(lambda: [0.0, 0])
    total_samples = 0

    try:
        with OUT.open("a", newline="", buffering=1) as f:
            writer = csv.writer(f)
            if new_file:
                writer.writerow(CSV_HEADER)

            while not stop_event.is_set():
                now = datetime.now(_UTC)
                sess = session_label(now)

                for sym in pairs:
                    try:
                        # get_symbol_price() goes through _rpc() (BUG-01: 30s timeout)
                        px = await client.get_symbol_price(sym)
                        sp = spread_pips(px.bid, px.ask, sym)
                        row = csv_row(now, sym, sess, sp)
                        writer.writerow(row)
                        update_agg(agg, sym, sess, sp)
                        total_samples += 1
                    except (RuntimeError, asyncio.TimeoutError) as exc:
                        logger.warning("[%s] %s sample failed: %s", now.strftime("%H:%M:%S"), sym, exc)
                        await reconnect_if_needed(client, sym)

                # Heartbeat: killzone averages so far
                kz_keys = [k for k in agg if k[1] != "off" and agg[k][1] > 0]
                if kz_keys and total_samples % max(1, 60 // args.interval) == 0:
                    parts = " | ".join(
                        f"{s}/{sn[:3]} avg {agg[(s, sn)][0] / agg[(s, sn)][1]:.2f}p"
                        for (s, sn) in sorted(kz_keys)
                    )
                    print(
                        f"  [{now.strftime('%H:%M:%S')} {sess}] "
                        f"n={total_samples} {parts}",
                        end="\r",
                    )

                # Responsive sleep: wakes immediately on stop_event
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=args.interval)
                except asyncio.TimeoutError:
                    pass  # normal interval expiry — keep looping

    finally:
        try:
            await client.disconnect()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Disconnect error: %s", exc)

    # ── Report ────────────────────────────────────────────────────────────────
    print(f"\n\nTotal samples collected: {total_samples}")
    print("\n=== Killzone spread summary (paste into config/costs.json) ===")
    for line in build_summary(agg, args.commission_pips, pairs):
        print(line)
    print(
        "\nSet active_profile to 'vantage_measured' in config/costs.json "
        "after filling those values.\n"
    )
    print(f"Raw samples saved to: {OUT}")


if __name__ == "__main__":
    asyncio.run(main())
