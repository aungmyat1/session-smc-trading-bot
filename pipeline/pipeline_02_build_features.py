"""
pipeline/02_build_features.py
Feature Parquet Builder — pre-computes derived datasets from OHLCV Parquets.

Outputs (per symbol, under data/features/{SYMBOL}/):
  asian_range.parquet   — daily Asian session H/L/mid (00-07 UTC)
  session_range.parquet — London + NY session H/L/mid/type per day

Session hours fixed to CLAUDE.md spec: London 07-10 UTC | NY 13-16 UTC.
(Archive prototype used 08-16 / 13-21 — now corrected.)

Run:
    python -m pipeline.02_build_features [--symbol EURUSD] [--all]
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from typing import Optional

import polars as pl

from .config import (
    ASIAN_WINDOW,
    DATA_DIR,
    FEATURES_DIR,
    PIP,
    SESSIONS,
    SIGNAL_CONFIG,
    SYMBOLS,
)
from session_smc.liquidity_detector import build_session_range, classify_session

_UTC = timezone.utc


# ── Polars → candle-dict helpers ──────────────────────────────────────────────

def _df_to_candles(df: pl.DataFrame) -> list[dict]:
    """Convert a Polars frame to list[dict] with key 'time' (not 'timestamp')."""
    if "timestamp" in df.columns and "time" not in df.columns:
        df = df.rename({"timestamp": "time"})
    rows = df.to_dicts()
    for r in rows:
        t = r.get("time")
        if isinstance(t, datetime) and t.tzinfo is None:
            r["time"] = t.replace(tzinfo=_UTC)
    return rows


def _load_tf(symbol: str, tf: str) -> Optional[pl.DataFrame]:
    path = DATA_DIR / symbol / f"{symbol}_{tf}.parquet"
    if not path.exists():
        return None
    df = pl.read_parquet(path)
    # Normalise timestamp column name → "timestamp"
    if "time" in df.columns and "timestamp" not in df.columns:
        df = df.rename({"time": "timestamp"})
    if "timestamp" not in df.columns:
        raise ValueError(f"{path}: no timestamp/time column found")
    df = df.with_columns(pl.col("timestamp").cast(pl.Datetime("us", "UTC")))
    return df.sort("timestamp")


# ── Asian range ───────────────────────────────────────────────────────────────

def build_asian_ranges(symbol: str) -> pl.DataFrame:
    """
    Compute the Asian session H/L/mid for every UTC calendar day.
    Uses M1 data (highest resolution available).
    Falls back to M15 if M1 not present.
    """
    df = _load_tf(symbol, "M1") or _load_tf(symbol, "M15")
    if df is None:
        print(f"  [{symbol}] No M1/M15 data — skipping Asian range build")
        return pl.DataFrame()

    w = ASIAN_WINDOW
    asian = (
        df.filter(
            (pl.col("timestamp").dt.hour() >= w.open_utc) &
            (pl.col("timestamp").dt.hour() < w.close_utc)
        )
        .with_columns(pl.col("timestamp").dt.date().alias("date"))
        .group_by("date")
        .agg([
            pl.col("high").max().alias("asian_high"),
            pl.col("low").min().alias("asian_low"),
            pl.col("volume").sum().alias("asian_volume"),
        ])
        .with_columns([
            ((pl.col("asian_high") + pl.col("asian_low")) / 2).alias("asian_mid"),
            ((pl.col("asian_high") - pl.col("asian_low")) / PIP).alias("asian_range_pips"),
            pl.lit(symbol).alias("symbol"),
        ])
        .sort("date")
    )
    return asian


# ── Session ranges ────────────────────────────────────────────────────────────

def build_session_ranges(symbol: str) -> pl.DataFrame:
    """
    Compute session H/L/mid/classification for London and NY sessions.
    Uses M15 data (session_range_bars × 15M = the range-build window).
    """
    df_m15 = _load_tf(symbol, "M15")
    if df_m15 is None:
        print(f"  [{symbol}] No M15 data — skipping session range build")
        return pl.DataFrame()

    rows: list[dict] = []
    all_dates = sorted(df_m15.select(pl.col("timestamp").dt.date()).unique()["timestamp"].to_list())

    for d in all_dates:
        d_start = datetime(d.year, d.month, d.day, tzinfo=_UTC)
        for sess in SESSIONS:
            t_open  = d_start.replace(hour=sess.open_utc)
            t_close = d_start.replace(hour=sess.close_utc)

            sess_bars = (
                df_m15
                .filter(
                    (pl.col("timestamp") >= t_open) &
                    (pl.col("timestamp") < t_close)
                )
                .sort("timestamp")
            )
            if sess_bars.is_empty():
                continue

            candles = _df_to_candles(sess_bars)
            sr = build_session_range(
                candles,
                range_bars=SIGNAL_CONFIG["session_range_bars"],
                min_range_pips=SIGNAL_CONFIG["min_session_range_pips"],
            )
            if sr is None:
                continue

            sess_class = classify_session(candles, sr, SIGNAL_CONFIG["atr_period"])

            rows.append({
                "date":            d,
                "symbol":          symbol,
                "session":         sess.name,
                "session_high":    sr["high"],
                "session_low":     sr["low"],
                "session_mid":     sr["midpoint"],
                "session_range_pips": sr["range_pips"],
                "session_type":    sess_class,
            })

    if not rows:
        return pl.DataFrame()
    return pl.DataFrame(rows).sort(["date", "session"])


# ── Main ──────────────────────────────────────────────────────────────────────

def process_symbol(symbol: str) -> None:
    out_dir = FEATURES_DIR / symbol
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n=== {symbol} ===")

    asian = build_asian_ranges(symbol)
    if not asian.is_empty():
        out = out_dir / "asian_range.parquet"
        asian.write_parquet(out, compression="zstd")
        print(f"  asian_range.parquet  → {len(asian):,} days")

    sr = build_session_ranges(symbol)
    if not sr.is_empty():
        out = out_dir / "session_range.parquet"
        sr.write_parquet(out, compression="zstd")
        print(f"  session_range.parquet → {len(sr):,} sessions")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build SMC feature Parquets")
    parser.add_argument("--symbol", choices=SYMBOLS, help="Single symbol")
    parser.add_argument("--all", action="store_true", help="All symbols")
    args = parser.parse_args()

    targets = SYMBOLS if args.all or not args.symbol else [args.symbol]
    print("=" * 60)
    print("Feature Builder — Session/Asian Range")
    print("=" * 60)
    for sym in targets:
        process_symbol(sym)
    print("\nDone.")


if __name__ == "__main__":
    main()
