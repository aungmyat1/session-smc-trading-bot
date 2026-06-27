"""
Dukascopy institutional tick data downloader.

Downloads bi5 (LZMA-compressed binary) tick files from Dukascopy's public feed
and saves raw ticks as Parquet to data/raw/dukascopy/{SYMBOL}/{YEAR}/{MM}/ticks.parquet.

Usage:
    python scripts/download_dukascopy.py --symbols EURUSD GBPUSD --start 2021-01 --end 2026-06
    python scripts/download_dukascopy.py --symbols EURUSD --start 2021-01 --end 2021-12 --workers 5

    # Dry run: list months that would be downloaded (no download)
    python scripts/download_dukascopy.py --symbols EURUSD --start 2021-01 --dry-run

    # Force re-download even if file exists
    python scripts/download_dukascopy.py --symbols EURUSD --start 2021-01 --force

DO NOT run this automatically. Must be invoked explicitly.
CLAUDE.md §0: do not download data without explicit user instruction.
"""

import argparse
import asyncio
import json
import io
import logging
import lzma
import struct
import sys
from datetime import datetime, timezone
from time import perf_counter
from calendar import monthrange
from pathlib import Path

import aiohttp
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parent.parent
DATA_RAW = ROOT / "data" / "raw" / "dukascopy"

# Dukascopy URL template: month is 0-indexed
_URL = "https://datafeed.dukascopy.com/datafeed/{sym}/{year}/{month0:02d}/{day:02d}/{hour:02d}h_ticks.bi5"

# 20 bytes per tick: ms_offset, ask_raw, bid_raw, ask_vol, bid_vol
_TICK = struct.Struct(">IIIff")
_TICK_SIZE = 20

PRICE_DIV = {
    "EURUSD": 100_000,
    "GBPUSD": 100_000,
    "USDJPY": 100_000,
    "XAUUSD": 1_000,
}

# Dukascopy internal symbol names
DUKA_SYM = {
    "EURUSD": "EURUSD",
    "GBPUSD": "GBPUSD",
    "USDJPY": "USDJPY",
    "XAUUSD": "XAUUSD",
}

TICK_SCHEMA = pa.schema([
    ("timestamp_ms", pa.int64()),
    ("ask",          pa.float32()),
    ("bid",          pa.float32()),
    ("ask_vol",      pa.float32()),
    ("bid_vol",      pa.float32()),
])

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("dukascopy")


def _hour_epoch_ms(year: int, month: int, day: int, hour: int) -> int:
    return int(pd.Timestamp(year=year, month=month, day=day, hour=hour, tz="UTC").timestamp() * 1000)


def _decode_bi5(data: bytes, hour_epoch_ms: int, price_div: float) -> list:
    """Decode LZMA-compressed bi5 block into list of (ts_ms, ask, bid, ask_vol, bid_vol)."""
    try:
        raw = lzma.decompress(data)
    except lzma.LZMAError:
        return []

    ticks = []
    n = len(raw) // _TICK_SIZE
    for i in range(n):
        offset = i * _TICK_SIZE
        ms_off, ask_raw, bid_raw, av, bv = _TICK.unpack_from(raw, offset)
        ticks.append((
            hour_epoch_ms + ms_off,
            ask_raw / price_div,
            bid_raw / price_div,
            av,
            bv,
        ))
    return ticks


async def _fetch_hour(session: aiohttp.ClientSession, sem: asyncio.Semaphore,
                      sym: str, year: int, month: int, day: int, hour: int,
                      price_div: float, request_delay: float = 0.05,
                      max_retries: int = 5) -> tuple[list, dict]:
    url = _URL.format(sym=DUKA_SYM[sym], year=year, month0=month - 1, day=day, hour=hour)
    hour_ms = _hour_epoch_ms(year, month, day, hour)
    stats = {
        "url": url,
        "hour": f"{year:04d}-{month:02d}-{day:02d}T{hour:02d}:00:00Z",
        "attempts": 0,
        "retries": 0,
        "status": "pending",
        "rows": 0,
    }

    async with sem:
        for attempt in range(max_retries):
            stats["attempts"] = attempt + 1
            try:
                if request_delay > 0:
                    await asyncio.sleep(request_delay)
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status == 404:
                        stats["status"] = "missing"
                        return [], stats  # no data for this hour (weekend, holiday, etc.)
                    if resp.status in (429, 500, 502, 503, 504):
                        raise aiohttp.ClientResponseError(
                            request_info=resp.request_info,
                            history=resp.history,
                            status=resp.status,
                            message=f"retryable status {resp.status}",
                            headers=resp.headers,
                    )
                    resp.raise_for_status()
                    data = await resp.read()
                ticks = _decode_bi5(data, hour_ms, price_div)
                stats["status"] = "ok"
                stats["rows"] = len(ticks)
                return ticks, stats
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                if attempt >= max_retries - 1:
                    log.warning("fetch error %s: %s", url, e)
                    stats["status"] = "failed"
                    stats["error"] = str(e)
                    return [], stats
                backoff = min(10.0, 0.75 * (2 ** attempt))
                log.warning("retry %d/%d %s: %s (sleep %.2fs)",
                            attempt + 1, max_retries, url, e, backoff)
                stats["retries"] += 1
                await asyncio.sleep(backoff)


async def _download_month(sym: str, year: int, month: int, force: bool,
                           workers: int) -> int:
    """Download all hours for one month, write Parquet. Returns tick count."""
    out_path = DATA_RAW / sym / str(year) / f"{month:02d}" / "ticks.parquet"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    month_dir = out_path.parent
    meta_path = month_dir / "acquisition.json"

    if not force and out_path.exists():
        try:
            meta = pq.read_metadata(out_path)
            if meta.num_rows > 0:
                log.info("SKIP %s %d-%02d (%d rows cached)", sym, year, month, meta.num_rows)
                return 0
        except Exception:
            pass  # corrupted file — re-download

    price_div = PRICE_DIV[sym]
    _, days_in_month = monthrange(year, month)
    hours = [
        (year, month, d, h)
        for d in range(1, days_in_month + 1)
        for h in range(24)
    ]

    log.info("Downloading %s %d-%02d (%d hours)...", sym, year, month, len(hours))
    started_at = datetime.now(timezone.utc)
    started_perf = perf_counter()

    sem = asyncio.Semaphore(workers)
    connector = aiohttp.TCPConnector(limit=workers * 2)
    async with aiohttp.ClientSession(connector=connector) as http:
        tasks = [
            _fetch_hour(http, sem, sym, y, m, d, h, price_div)
            for y, m, d, h in hours
        ]
        results = await asyncio.gather(*tasks)

    all_ticks = []
    hour_stats = []
    for batch in results:
        ticks, stats = batch
        hour_stats.append(stats)
        all_ticks.extend(ticks)

    elapsed_seconds = perf_counter() - started_perf
    month_meta = {
        "symbol": sym,
        "year": year,
        "month": month,
        "month_key": f"{year:04d}-{month:02d}",
        "source": "dukascopy",
        "output_path": str(out_path.relative_to(ROOT)),
        "started_at": started_at.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": round(elapsed_seconds, 3),
        "rows": len(all_ticks),
        "hours_requested": len(hours),
        "hours_ok": sum(1 for item in hour_stats if item["status"] == "ok"),
        "hours_missing": sum(1 for item in hour_stats if item["status"] == "missing"),
        "hours_failed": sum(1 for item in hour_stats if item["status"] == "failed"),
        "retries": sum(item["retries"] for item in hour_stats),
        "max_attempts": max((item["attempts"] for item in hour_stats), default=0),
        "avg_rows_per_hour": round(len(all_ticks) / len(hours), 2) if hours else 0.0,
        "rows_per_second": round(len(all_ticks) / elapsed_seconds, 2) if elapsed_seconds > 0 else None,
        "cached": False,
    }

    if not all_ticks:
        log.warning("No ticks for %s %d-%02d (weekend/holiday month?)", sym, year, month)
        meta_path.write_text(json.dumps(month_meta, indent=2))
        log.info("Wrote acquisition metadata → %s", meta_path)
        return 0

    all_ticks.sort(key=lambda t: t[0])

    ts_ms   = pa.array([t[0] for t in all_ticks], type=pa.int64())
    ask_arr = pa.array([t[1] for t in all_ticks], type=pa.float32())
    bid_arr = pa.array([t[2] for t in all_ticks], type=pa.float32())
    av_arr  = pa.array([t[3] for t in all_ticks], type=pa.float32())
    bv_arr  = pa.array([t[4] for t in all_ticks], type=pa.float32())

    table = pa.table(
        {"timestamp_ms": ts_ms, "ask": ask_arr, "bid": bid_arr,
         "ask_vol": av_arr, "bid_vol": bv_arr},
        schema=TICK_SCHEMA,
    )
    pq.write_table(table, out_path, compression="snappy", row_group_size=100_000)
    log.info("Wrote %s %d-%02d → %d ticks → %s", sym, year, month, len(all_ticks), out_path)

    meta_path.write_text(json.dumps(month_meta, indent=2))
    log.info("Wrote acquisition metadata → %s", meta_path)
    return len(all_ticks)


def _parse_ym(s: str):
    parts = s.split("-")
    return int(parts[0]), int(parts[1])


def _month_range(start: str, end: str):
    sy, sm = _parse_ym(start)
    ey, em = _parse_ym(end)
    months = []
    y, m = sy, sm
    while (y, m) <= (ey, em):
        months.append((y, m))
        m += 1
        if m > 12:
            m = 1
            y += 1
    return months


async def _main_async(symbols, months, force, workers, dry_run):
    total = 0
    for sym in symbols:
        if sym not in PRICE_DIV:
            log.error("Unknown symbol %s. Supported: %s", sym, list(PRICE_DIV.keys()))
            sys.exit(1)
        for year, month in months:
            if dry_run:
                out = DATA_RAW / sym / str(year) / f"{month:02d}" / "ticks.parquet"
                exists = out.exists()
                log.info("DRY-RUN %s %d-%02d → %s", sym, year, month,
                         "EXISTS" if exists else "WOULD DOWNLOAD")
                continue
            count = await _download_month(sym, year, month, force, workers)
            total += count
    if not dry_run:
        log.info("Done. Total ticks downloaded this run: %d", total)


def main():
    parser = argparse.ArgumentParser(description="Dukascopy raw tick downloader")
    parser.add_argument("--symbols", nargs="+", default=["EURUSD", "GBPUSD"],
                        help="Symbols to download (default: EURUSD GBPUSD)")
    parser.add_argument("--start", required=True, help="Start year-month e.g. 2021-01")
    parser.add_argument("--end", required=True, help="End year-month e.g. 2026-06")
    parser.add_argument("--workers", type=int, default=8, help="Concurrent HTTP workers")
    parser.add_argument("--force", action="store_true", help="Re-download even if cached")
    parser.add_argument("--dry-run", action="store_true", help="List months only, no download")
    args = parser.parse_args()

    months = _month_range(args.start, args.end)
    log.info("Pipeline: %d symbol(s) × %d months = %d month-downloads",
             len(args.symbols), len(months), len(args.symbols) * len(months))

    asyncio.run(_main_async(args.symbols, months, args.force, args.workers, args.dry_run))


if __name__ == "__main__":
    main()
