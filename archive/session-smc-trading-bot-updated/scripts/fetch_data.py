#!/usr/bin/env python3
"""
Fetch historical OHLCV data from Dukascopy public datafeed.
No account or API key required — data is free and publicly accessible.

Dukascopy URL format:
  https://datafeed.dukascopy.com/datafeed/{SYMBOL}/{YEAR}/{MONTH_0IDX:02d}/{DAY:02d}/{HOUR:02d}h_ticks.bi5
  NOTE: months are 0-indexed (Jan=00, Feb=01, ..., Dec=11).

bi5 binary format (20 bytes/tick, big-endian):
  [4B uint32]  milliseconds from start of clock hour
  [4B uint32]  ask price × 100 000
  [4B uint32]  bid price × 100 000
  [4B float32] ask volume
  [4B float32] bid volume

Output files (compatible with scripts/backtest.py):
  data/historical/{PAIR}_{TF}.csv
  e.g. EUR_USD_M15.csv, EUR_USD_H1.csv, EUR_USD_H4.csv
  Columns: time, open, high, low, close, volume

Usage:
  python3 scripts/fetch_data.py                         # all pairs, M15+H1+H4, 5yr
  python3 scripts/fetch_data.py --symbols EURUSD        # single pair
  python3 scripts/fetch_data.py --granularities M15 H4  # subset of timeframes
  python3 scripts/fetch_data.py --start 2022-01-01      # custom start date

First-run estimate: ~60-90 min for 5yr of EURUSD+GBPUSD (network-dependent).
Subsequent runs are incremental — only missing days are downloaded.
"""

import argparse
import asyncio
import csv
import lzma
import struct
import sys
from datetime import date, datetime, timezone, timedelta
from pathlib import Path

try:
    import aiohttp
except ImportError:
    sys.exit("Install aiohttp: pip install aiohttp")

# ── Config ────────────────────────────────────────────────────────────────────

_DUKA_BASE = "https://datafeed.dukascopy.com/datafeed"

# dukascopy symbol → csv file prefix
SYMBOLS: dict[str, str] = {
    "EURUSD": "EUR_USD",
    "GBPUSD": "GBP_USD",
}

DEFAULT_GRANULARITIES = ["M15", "H1", "H4"]
YEARS_BACK = 5
MAX_CONCURRENT = 8  # parallel hour-file downloads
_RETRY_SLEEP = 1.0  # seconds between retry attempts

OUTPUT_DIR = Path(__file__).parent.parent / "data" / "historical"
_FIELDNAMES = ["time", "open", "high", "low", "close", "volume"]

# minutes per bar for each supported granularity
_TF_MINUTES: dict[str, int] = {"M15": 15, "H1": 60, "H4": 240}

# bi5 struct: big-endian 5 fields × 4 bytes = 20 bytes/tick
_TICK = struct.Struct(">IIIff")
_PRICE_DIV = 100_000.0


# ── URL builder ───────────────────────────────────────────────────────────────


def _hour_url(duka_sym: str, dt: datetime) -> str:
    """Build Dukascopy datafeed URL for a specific clock hour. Month is 0-indexed."""
    return (
        f"{_DUKA_BASE}/{duka_sym}"
        f"/{dt.year}/{dt.month - 1:02d}/{dt.day:02d}/{dt.hour:02d}h_ticks.bi5"
    )


# ── Download + parse one hour file ───────────────────────────────────────────


async def _fetch_hour(
    session: aiohttp.ClientSession,
    sem: asyncio.Semaphore,
    duka_sym: str,
    hour_dt: datetime,
) -> list[tuple[datetime, float, float]]:
    """
    Download and parse one hour of tick data.
    Returns [(timestamp_utc, mid_price, volume), ...].
    Empty list on 404 (weekend/holiday), bad data, or network error.
    """
    url = _hour_url(duka_sym, hour_dt)

    async with sem:
        raw = b""
        for attempt in range(2):
            try:
                async with session.get(
                    url, timeout=aiohttp.ClientTimeout(total=25)
                ) as r:
                    if r.status in (404, 204):
                        return []
                    if r.status != 200:
                        if attempt == 0:
                            await asyncio.sleep(_RETRY_SLEEP)
                            continue
                        return []
                    raw = await r.read()
                    break
            except Exception:
                if attempt == 0:
                    await asyncio.sleep(_RETRY_SLEEP)
                    continue
                return []

    if not raw:
        return []

    try:
        data = lzma.decompress(raw)
    except lzma.LZMAError:
        # Fall back to raw LZMA format (no XZ container)
        try:
            data = lzma.decompress(raw, format=lzma.FORMAT_ALONE)
        except lzma.LZMAError:
            return []

    ticks: list[tuple[datetime, float, float]] = []
    size = _TICK.size
    for off in range(0, len(data) - size + 1, size):
        ms, ask_raw, bid_raw, ask_vol, bid_vol = _TICK.unpack_from(data, off)
        ts = hour_dt + timedelta(milliseconds=int(ms))
        mid = (ask_raw + bid_raw) / 2 / _PRICE_DIV
        ticks.append((ts, mid, float(ask_vol + bid_vol)))

    return ticks


# ── Aggregate ticks → OHLCV candles ──────────────────────────────────────────


def _to_ohlcv(
    ticks: list[tuple[datetime, float, float]],
    tf_minutes: int,
) -> list[dict]:
    """
    Group ticks into fixed-width UTC candles at tf_minutes resolution.
    Returns list of OHLCV dicts sorted by time.
    H4 boundaries align to UTC midnight (00:00, 04:00, 08:00, 12:00, 16:00, 20:00).
    """
    bins: dict[str, dict] = {}
    for ts, mid, vol in ticks:
        # Floor ts to tf_minutes boundary counting from midnight UTC
        minutes_into_day = ts.hour * 60 + ts.minute
        bin_minutes = (minutes_into_day // tf_minutes) * tf_minutes
        bin_start = ts.replace(
            hour=bin_minutes // 60,
            minute=bin_minutes % 60,
            second=0,
            microsecond=0,
        )
        label = bin_start.strftime("%Y-%m-%dT%H:%M:%SZ")
        if label not in bins:
            bins[label] = {
                "time": label,
                "open": mid,
                "high": mid,
                "low": mid,
                "close": mid,
                "volume": 0.0,
            }
        b = bins[label]
        if mid > b["high"]:
            b["high"] = mid
        if mid < b["low"]:
            b["low"] = mid
        b["close"] = mid
        b["volume"] += vol

    result = sorted(bins.values(), key=lambda x: x["time"])
    for c in result:
        for k in ("open", "high", "low", "close"):
            c[k] = round(c[k], 5)
        c["volume"] = round(c["volume"], 2)
    return result


# ── CSV helpers ───────────────────────────────────────────────────────────────


def _load(path: Path) -> dict[str, dict]:
    """Load CSV into {time_str: row_dict} for O(1) upsert."""
    if not path.exists():
        return {}
    rows: dict[str, dict] = {}
    with open(path) as f:
        for row in csv.DictReader(f):
            rows[row["time"]] = {
                "time": row["time"],
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": float(row.get("volume", 0)),
            }
    return rows


def _save(cache: dict[str, dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sorted_rows = sorted(cache.values(), key=lambda x: x["time"])
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=_FIELDNAMES)
        w.writeheader()
        w.writerows(sorted_rows)


# ── Per-symbol fetch ──────────────────────────────────────────────────────────


async def fetch_symbol(
    duka_sym: str,
    csv_sym: str,
    start: date,
    end: date,
    granularities: list[str],
) -> None:
    """Download tick data for one symbol and write OHLCV CSVs."""

    # Load existing caches and find latest day already saved
    caches = {
        gran: _load(OUTPUT_DIR / f"{csv_sym}_{gran}.csv") for gran in granularities
    }
    resume = start
    for cache in caches.values():
        if cache:
            last_ts = max(cache.keys())
            last_d = datetime.fromisoformat(last_ts.replace("Z", "+00:00")).date()
            if last_d > resume:
                resume = last_d  # re-fetch last partial day for safety

    # Count trading days for progress display (approximate)
    trading_days = sum(
        1
        for n in range((end - resume).days + 1)
        if (resume + timedelta(days=n)).weekday() < 5
    )

    day = resume
    done = 0

    sem = asyncio.Semaphore(MAX_CONCURRENT)
    connector = aiohttp.TCPConnector(limit=MAX_CONCURRENT + 2, force_close=True)
    async with aiohttp.ClientSession(connector=connector) as http:
        while day <= end:
            if day.weekday() >= 5:  # Sat/Sun — forex market closed
                day += timedelta(days=1)
                continue

            # Download all 24 clock hours for this day concurrently
            hours = [
                datetime(day.year, day.month, day.day, h, tzinfo=timezone.utc)
                for h in range(24)
            ]
            results = await asyncio.gather(
                *[_fetch_hour(http, sem, duka_sym, h) for h in hours],
                return_exceptions=True,
            )

            day_ticks: list[tuple[datetime, float, float]] = []
            for r in results:
                if isinstance(r, list):
                    day_ticks.extend(r)

            # Aggregate ticks into each requested timeframe and upsert into cache
            if day_ticks:
                for gran in granularities:
                    for c in _to_ohlcv(day_ticks, _TF_MINUTES[gran]):
                        caches[gran][c["time"]] = c

            done += 1
            pct = done / max(trading_days, 1) * 100
            print(
                f"  {duka_sym} {day}  ticks={len(day_ticks):5d}  [{pct:5.1f}%]",
                end="\r",
                flush=True,
            )
            day += timedelta(days=1)

    print()  # newline after carriage-return progress

    # Write updated CSVs
    for gran in granularities:
        path = OUTPUT_DIR / f"{csv_sym}_{gran}.csv"
        _save(caches[gran], path)
        print(f"  [{csv_sym}/{gran}]  {len(caches[gran]):6d} bars  →  {path.name}")


# ── Entry point ───────────────────────────────────────────────────────────────


async def _run(
    symbols: list[str],
    granularities: list[str],
    start_str: str,
    end_str: str | None = None,
) -> None:
    bad_tf = [g for g in granularities if g not in _TF_MINUTES]
    if bad_tf:
        sys.exit(f"Unknown granularity: {bad_tf}. Supported: {list(_TF_MINUTES)}")

    start = datetime.strptime(start_str, "%Y-%m-%d").date()
    if end_str:
        end = datetime.strptime(end_str, "%Y-%m-%d").date()
    else:
        end = (datetime.now(timezone.utc) - timedelta(days=1)).date()

    if start > end:
        sys.exit(f"Start date {start} is after end date {end}.")

    for sym in symbols:
        if sym not in SYMBOLS:
            print(
                f"Unknown symbol {sym!r}. Available: {list(SYMBOLS)}", file=sys.stderr
            )
            continue
        print(f"\n[{sym}]  {start} → {end}  ({', '.join(granularities)})")
        await fetch_symbol(sym, SYMBOLS[sym], start, end, granularities)


def main() -> None:
    default_start = (
        datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        - timedelta(days=365 * YEARS_BACK)
    ).strftime("%Y-%m-%d")

    p = argparse.ArgumentParser(
        description="Fetch Dukascopy historical forex candles — no API key needed",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python3 scripts/fetch_data.py\n"
            "  python3 scripts/fetch_data.py --symbols EURUSD\n"
            "  python3 scripts/fetch_data.py --start 2022-01-01 --granularities M15 H4\n"
        ),
    )
    p.add_argument(
        "--symbols",
        nargs="+",
        default=list(SYMBOLS),
        metavar="SYM",
        help=f"Pairs to fetch. Default: {list(SYMBOLS)}",
    )
    p.add_argument(
        "--granularities",
        nargs="+",
        default=DEFAULT_GRANULARITIES,
        metavar="TF",
        help=f"Timeframes. Default: {DEFAULT_GRANULARITIES}. Supported: {list(_TF_MINUTES)}",
    )
    p.add_argument(
        "--start",
        default=default_start,
        metavar="YYYY-MM-DD",
        help=f"Earliest date to fetch. Default: {default_start}",
    )
    p.add_argument(
        "--end",
        default=None,
        metavar="YYYY-MM-DD",
        help="Latest date to fetch (inclusive). Default: yesterday",
    )
    args = p.parse_args()
    asyncio.run(_run(args.symbols, args.granularities, args.start, args.end))


if __name__ == "__main__":
    main()
