"""
Build OHLCV Parquet files from raw tick Parquet.

Reads data/raw/dukascopy/{SYMBOL}/{YEAR}/{MM}/ticks.parquet
Writes data/processed/{SYMBOL}/{TF}.parquet

Usage:
    python scripts/build_timeframes.py --symbols EURUSD GBPUSD
    python scripts/build_timeframes.py --symbols EURUSD --timeframes M15 H1 H4
    python scripts/build_timeframes.py --symbols EURUSD --start 2021-01 --end 2022-12

Supported timeframes: M1, M5, M15, H1, H4, D1
"""

import argparse
import logging
import os
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parent.parent
DATA_RAW = ROOT / "data" / "raw" / "dukascopy"
DATA_PROC = ROOT / "data" / "processed"

TIMEFRAMES = {
    "M1":  "1min",
    "M5":  "5min",
    "M15": "15min",
    "H1":  "1h",
    "H4":  "4h",
    "D1":  "1D",
}

OHLCV_SCHEMA = pa.schema([
    ("timestamp_utc", pa.timestamp("ns", tz="UTC")),
    ("open",          pa.float64()),
    ("high",          pa.float64()),
    ("low",           pa.float64()),
    ("close",         pa.float64()),
    ("volume",        pa.float64()),
    ("ask_open",      pa.float32()),
    ("bid_open",      pa.float32()),
    ("spread_avg",    pa.float32()),
    ("spread_max",    pa.float32()),
    ("tick_count",    pa.int32()),
])

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("build_tf")


def _load_month_ticks(sym: str, year: int, month: int) -> pd.DataFrame | None:
    path = DATA_RAW / sym / str(year) / f"{month:02d}" / "ticks.parquet"
    if not path.exists():
        return None
    df = pd.read_parquet(path)
    if df.empty:
        return None
    df["timestamp_utc"] = pd.to_datetime(df["timestamp_ms"], unit="ms", utc=True)
    df["mid"] = (df["ask"] + df["bid"]) / 2.0
    df["spread"] = df["ask"] - df["bid"]
    return df


def _resample_to_ohlcv(ticks: pd.DataFrame, freq: str) -> pd.DataFrame:
    ticks = ticks.set_index("timestamp_utc").sort_index()
    mid = ticks["mid"]
    ask = ticks["ask"]
    bid = ticks["bid"]
    spread = ticks["spread"]
    vol = ticks["ask_vol"] + ticks["bid_vol"]

    bars = pd.DataFrame({
        "open":       mid.resample(freq).first(),
        "high":       mid.resample(freq).max(),
        "low":        mid.resample(freq).min(),
        "close":      mid.resample(freq).last(),
        "volume":     vol.resample(freq).sum(),
        "ask_open":   ask.resample(freq).first().astype("float32"),
        "bid_open":   bid.resample(freq).first().astype("float32"),
        "spread_avg": spread.resample(freq).mean().astype("float32"),
        "spread_max": spread.resample(freq).max().astype("float32"),
        "tick_count": mid.resample(freq).count().astype("int32"),
    })
    bars = bars.dropna(subset=["open"])
    bars = bars[bars["tick_count"] > 0]
    return bars.reset_index()


def _available_months(sym: str) -> list[tuple[int, int]]:
    sym_dir = DATA_RAW / sym
    if not sym_dir.exists():
        return []
    months = []
    for year_dir in sorted(sym_dir.iterdir()):
        if not year_dir.is_dir():
            continue
        try:
            year = int(year_dir.name)
        except ValueError:
            continue
        for month_dir in sorted(year_dir.iterdir()):
            if not month_dir.is_dir():
                continue
            try:
                month = int(month_dir.name)
            except ValueError:
                continue
            tick_file = month_dir / "ticks.parquet"
            if tick_file.exists():
                months.append((year, month))
    return months


def build_symbol(sym: str, tfs: list[str], start_ym: tuple | None, end_ym: tuple | None):
    months = _available_months(sym)
    if not months:
        log.error("No raw ticks found for %s at %s — run download_dukascopy.py first", sym, DATA_RAW / sym)
        return

    if start_ym:
        months = [(y, m) for y, m in months if (y, m) >= start_ym]
    if end_ym:
        months = [(y, m) for y, m in months if (y, m) <= end_ym]

    if not months:
        log.warning("No months in requested range for %s", sym)
        return

    log.info("%s: loading %d months of raw ticks", sym, len(months))

    out_dir = DATA_PROC / sym
    out_dir.mkdir(parents=True, exist_ok=True)
    month_frames_by_tf = {tf: [] for tf in tfs}
    total_ticks = 0
    loaded_months = 0

    for year, month in months:
        df = _load_month_ticks(sym, year, month)
        if df is None:
            continue
        loaded_months += 1
        total_ticks += len(df)
        log.debug("  loaded %s %d-%02d: %d ticks", sym, year, month, len(df))
        for tf in tfs:
            freq = TIMEFRAMES[tf]
            bars = _resample_to_ohlcv(df, freq)
            if not bars.empty:
                month_frames_by_tf[tf].append(bars)

    if loaded_months == 0:
        log.error("All months empty for %s", sym)
        return

    log.info("%s: %d total ticks loaded", sym, total_ticks)

    for tf in tfs:
        frames = month_frames_by_tf[tf]
        if not frames:
            log.warning("%s %s: no bars produced", sym, tf)
            continue
        bars = pd.concat(frames, ignore_index=True).sort_values("timestamp_utc").reset_index(drop=True)
        out_path = out_dir / f"{tf}.parquet"
        table = pa.Table.from_pandas(bars, schema=OHLCV_SCHEMA, preserve_index=False)
        # Never leave a partially-written canonical dataset if a build is interrupted.
        tmp_path = out_path.with_suffix(".parquet.tmp")
        pq.write_table(table, tmp_path, compression="snappy", row_group_size=50_000)
        os.replace(tmp_path, out_path)
        log.info("%s %s: %d bars → %s", sym, tf, len(bars), out_path)


def main():
    parser = argparse.ArgumentParser(description="Build OHLCV Parquet from raw ticks")
    parser.add_argument("--symbols", nargs="+", default=["EURUSD", "GBPUSD"])
    parser.add_argument("--timeframes", nargs="+", default=list(TIMEFRAMES.keys()),
                        choices=list(TIMEFRAMES.keys()))
    parser.add_argument("--start", help="Start year-month e.g. 2021-01")
    parser.add_argument("--end", help="End year-month e.g. 2026-06")
    args = parser.parse_args()

    def parse_ym(s):
        y, m = s.split("-")
        return int(y), int(m)

    start_ym = parse_ym(args.start) if args.start else None
    end_ym   = parse_ym(args.end)   if args.end   else None

    for sym in args.symbols:
        build_symbol(sym, args.timeframes, start_ym, end_ym)

    log.info("Done.")


if __name__ == "__main__":
    main()
