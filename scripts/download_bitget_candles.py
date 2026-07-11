#!/usr/bin/env python3
"""Download Bitget spot candles and build canonical processed Parquet bars.

The professional dataset uses BTCUSD as the canonical research symbol, while
Bitget's liquid spot market is BTCUSDT. This script records that source mapping
in metadata and writes the repo's legacy processed schema so downstream tools can
read BTC alongside FX/XAUUSD.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import requests
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
DATA_RAW = ROOT / "data" / "raw" / "bitget"
DATA_PROC = ROOT / "data" / "processed"

API_URL = "https://api.bitget.com/api/v2/spot/market/history-candles"
TIMEFRAME_FREQ = {
    "M5": "5min",
    "M15": "15min",
    "H1": "1h",
    "H4": "4h",
    "D1": "1D",
}
BITGET_GRANULARITY = {
    "M5": "5min",
}

OHLCV_SCHEMA = pa.schema(
    [
        ("timestamp_utc", pa.timestamp("ns", tz="UTC")),
        ("open", pa.float64()),
        ("high", pa.float64()),
        ("low", pa.float64()),
        ("close", pa.float64()),
        ("volume", pa.float64()),
        ("ask_open", pa.float32()),
        ("bid_open", pa.float32()),
        ("spread_avg", pa.float32()),
        ("spread_max", pa.float32()),
        ("tick_count", pa.int32()),
    ]
)


def _parse_ym(value: str) -> tuple[int, int]:
    year, month = value.split("-", 1)
    return int(year), int(month)


def _month_start(year: int, month: int) -> pd.Timestamp:
    return pd.Timestamp(year=year, month=month, day=1, tz="UTC")


def _window_bounds(start_ym: str, end_ym: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    start_year, start_month = _parse_ym(start_ym)
    end_year, end_month = _parse_ym(end_ym)
    start = _month_start(start_year, start_month)
    if end_month == 12:
        end = _month_start(end_year + 1, 1)
    else:
        end = _month_start(end_year, end_month + 1)
    return start, end


def _request_page(
    session: requests.Session,
    source_symbol: str,
    granularity: str,
    end_ms: int,
    timeout_seconds: float,
    max_retries: int,
) -> list[list[str]]:
    params = {
        "symbol": source_symbol,
        "granularity": granularity,
        "endTime": str(end_ms),
        "limit": "200",
    }
    last_error: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            response = session.get(API_URL, params=params, timeout=timeout_seconds)
            response.raise_for_status()
            payload = response.json()
            if payload.get("code") != "00000":
                raise RuntimeError(f"Bitget error {payload.get('code')}: {payload.get('msg')}")
            return payload.get("data") or []
        except Exception as exc:  # noqa: BLE001 - retry and surface final error.
            last_error = exc
            sleep_seconds = min(2.0 + attempt, 10.0)
            time.sleep(sleep_seconds)
    raise RuntimeError(f"Bitget request failed after {max_retries + 1} attempts: {last_error}")


def _fetch_m5(
    canonical_symbol: str,
    source_symbol: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
    timeout_seconds: float,
    max_retries: int,
) -> pd.DataFrame:
    session = requests.Session()
    granularity = BITGET_GRANULARITY["M5"]
    start_ms = int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000)
    rows: list[list[str]] = []
    pages = 0

    while end_ms > start_ms:
        page = _request_page(session, source_symbol, granularity, end_ms, timeout_seconds, max_retries)
        if not page:
            break
        pages += 1
        rows.extend(page)
        min_ts = min(int(item[0]) for item in page)
        if min_ts <= start_ms:
            break
        if min_ts >= end_ms:
            raise RuntimeError(f"Bitget pagination did not move backward for {canonical_symbol}")
        end_ms = min_ts
        time.sleep(0.06)

    if not rows:
        raise RuntimeError(f"No Bitget candles returned for {source_symbol}")

    df = pd.DataFrame(
        rows,
        columns=[
            "timestamp_ms",
            "open",
            "high",
            "low",
            "close",
            "base_volume",
            "usdt_volume",
            "quote_volume",
        ],
    )
    numeric_cols = ["open", "high", "low", "close", "base_volume", "usdt_volume", "quote_volume"]
    for column in numeric_cols:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    df["timestamp_utc"] = pd.to_datetime(pd.to_numeric(df["timestamp_ms"]), unit="ms", utc=True)
    df = df[(df["timestamp_utc"] >= start) & (df["timestamp_utc"] < end)]
    df = df.dropna(subset=["open", "high", "low", "close"])
    df = df.drop_duplicates(subset=["timestamp_utc"]).sort_values("timestamp_utc").reset_index(drop=True)
    if df.empty:
        raise RuntimeError(f"No Bitget candles remained inside requested window for {source_symbol}")
    print(f"{canonical_symbol}: downloaded {len(df):,} M5 candles from {source_symbol} in {pages} pages")
    return df


def _to_processed_schema(df: pd.DataFrame) -> pd.DataFrame:
    bars = pd.DataFrame(
        {
            "timestamp_utc": df["timestamp_utc"],
            "open": df["open"].astype("float64"),
            "high": df["high"].astype("float64"),
            "low": df["low"].astype("float64"),
            "close": df["close"].astype("float64"),
            "volume": df["base_volume"].astype("float64"),
            "ask_open": df["open"].astype("float32"),
            "bid_open": df["open"].astype("float32"),
            "spread_avg": np.nan,
            "spread_max": np.nan,
            "tick_count": 1,
        }
    )
    bars["spread_avg"] = bars["spread_avg"].astype("float32")
    bars["spread_max"] = bars["spread_max"].astype("float32")
    bars["tick_count"] = bars["tick_count"].astype("int32")
    return bars


def _resample(processed_m5: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    if timeframe == "M5":
        return processed_m5.copy()

    freq = TIMEFRAME_FREQ[timeframe]
    indexed = processed_m5.set_index("timestamp_utc").sort_index()
    bars = pd.DataFrame(
        {
            "open": indexed["open"].resample(freq).first(),
            "high": indexed["high"].resample(freq).max(),
            "low": indexed["low"].resample(freq).min(),
            "close": indexed["close"].resample(freq).last(),
            "volume": indexed["volume"].resample(freq).sum(),
            "ask_open": indexed["ask_open"].resample(freq).first().astype("float32"),
            "bid_open": indexed["bid_open"].resample(freq).first().astype("float32"),
            "spread_avg": indexed["spread_avg"].resample(freq).mean().astype("float32"),
            "spread_max": indexed["spread_max"].resample(freq).max().astype("float32"),
            "tick_count": indexed["tick_count"].resample(freq).sum().astype("int32"),
        }
    )
    bars = bars.dropna(subset=["open", "high", "low", "close"])
    bars = bars[bars["tick_count"] > 0]
    return bars.reset_index()


def _write_parquet(path: Path, df: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".parquet.tmp")
    table = pa.Table.from_pandas(df, schema=OHLCV_SCHEMA, preserve_index=False)
    pq.write_table(table, tmp_path, compression="snappy", row_group_size=50_000)
    os.replace(tmp_path, path)


def _write_metadata(
    canonical_symbol: str,
    source_symbol: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
    timeframes: list[str],
    raw_path: Path,
) -> None:
    metadata: dict[str, Any] = {
        "canonical_symbol": canonical_symbol,
        "source": "bitget_spot",
        "source_symbol": source_symbol,
        "api_url": API_URL,
        "window_start": start.isoformat(),
        "window_end_exclusive": end.isoformat(),
        "raw_timeframe": "M5",
        "processed_timeframes": timeframes,
        "spread_available": False,
        "spread_note": "Bitget public candle endpoint provides OHLCV only, not bid/ask spread.",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "raw_path": str(raw_path.relative_to(ROOT)),
    }
    out_path = DATA_PROC / canonical_symbol / "source_metadata.json"
    out_path.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Download Bitget spot candles into processed Parquet bars")
    parser.add_argument("--symbol", default="BTCUSD", help="Canonical dataset symbol")
    parser.add_argument("--source-symbol", default="BTCUSDT", help="Bitget spot trading pair")
    parser.add_argument("--start", required=True, help="Start year-month, e.g. 2023-07")
    parser.add_argument("--end", required=True, help="End year-month, e.g. 2026-06")
    parser.add_argument("--timeframes", nargs="+", default=["M5", "M15", "H1", "H4"], choices=list(TIMEFRAME_FREQ))
    parser.add_argument("--timeout-seconds", type=float, default=20.0)
    parser.add_argument("--max-retries", type=int, default=5)
    args = parser.parse_args()

    start, end = _window_bounds(args.start, args.end)
    raw_df = _fetch_m5(args.symbol, args.source_symbol, start, end, args.timeout_seconds, args.max_retries)

    raw_dir = DATA_RAW / args.symbol / "M5"
    raw_path = raw_dir / f"{args.start}_{args.end}.parquet"
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_tmp = raw_path.with_suffix(".parquet.tmp")
    pq.write_table(pa.Table.from_pandas(raw_df, preserve_index=False), raw_tmp, compression="snappy", row_group_size=50_000)
    os.replace(raw_tmp, raw_path)

    processed_m5 = _to_processed_schema(raw_df)
    for timeframe in args.timeframes:
        bars = _resample(processed_m5, timeframe)
        out_path = DATA_PROC / args.symbol / f"{timeframe}.parquet"
        _write_parquet(out_path, bars)
        print(f"{args.symbol} {timeframe}: wrote {len(bars):,} bars -> {out_path}")

    _write_metadata(args.symbol, args.source_symbol, start, end, args.timeframes, raw_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
