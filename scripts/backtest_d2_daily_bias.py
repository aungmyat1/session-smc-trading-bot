"""
backtest_d2_daily_bias.py — support module for optimize_d2_rules.py

Provides:
  OUTDIR              — directory where prepared 5m/15m CSV data files are cached
  add_context(df)     — add PDH, PDL, htf_trend columns to an OHLCV+spread DataFrame
  pivot_swings(df)    — add pivot_high_level, pivot_low_level (rolling lookback)
  PIP_SIZE            — {'EURUSD': 0.0001, 'GBPUSD': 0.0001}
  INITIAL_CAPITAL     — 10_000
  RISK_PER_TRADE      — 0.01
  SL_BUFFER_PIPS      — {'EURUSD': 2.0, 'GBPUSD': 2.0}
  SPREAD_FILTER_MULT  — 2.5

Data source: data/historical/{EUR,GBP}_USD_M15.csv (M15 bars used in place of 5m;
confirm_bars in the optimizer therefore represent 15-min intervals, not 5-min).

Run as __main__ to prepare the cached CSV files (idempotent):
    python3 scripts/backtest_d2_daily_bias.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

# ── Directories ───────────────────────────────────────────────────────────────

_ROOT = Path(__file__).parent.parent
# OUTDIR is where the prepared CSV files live — optimizer imports this as DATA_DIR
OUTDIR = _ROOT / "backtest_output_d2_data"
OUTDIR.mkdir(exist_ok=True)

_HIST_DIR = _ROOT / "data" / "historical"

# ── Constants ─────────────────────────────────────────────────────────────────

PIP_SIZE: dict[str, float] = {"EURUSD": 0.0001, "GBPUSD": 0.0001}

INITIAL_CAPITAL: float = 10_000.0
RISK_PER_TRADE: float = 0.005         # 0.5 % per trade (ST-D2-E3-OPT2 spec)
SL_BUFFER_PIPS: dict[str, float] = {"EURUSD": 2.0, "GBPUSD": 2.0}
SPREAD_FILTER_MULT: float = 2.5

# Synthetic constant spread (pips × pip_size) — M15 CSVs have no spread column
_SYNTH_SPREAD: dict[str, float] = {
    "EURUSD": 1.4 * PIP_SIZE["EURUSD"],   # 0.00014
    "GBPUSD": 1.8 * PIP_SIZE["GBPUSD"],   # 0.00018
}

_SYMBOL_FILE: dict[str, str] = {
    "EURUSD": "EUR_USD_M15.csv",
    "GBPUSD": "GBP_USD_M15.csv",
}

_DATE_START = "2025-12-01"
_DATE_END   = "2026-05-31"

# ── add_context ───────────────────────────────────────────────────────────────

def add_context(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add D2 context columns to an OHLCV+spread DataFrame.

    Input : DataFrame with UTC DatetimeIndex, columns open/high/low/close/spread.
    Output: same + pdh, pdl (previous calendar day H/L), htf_trend ('bullish'|'bearish').
    """
    df = df.copy()

    # ── PDH / PDL ──────────────────────────────────────────────────────────────
    date_idx = df.index.floor("D")          # UTC day for each bar
    daily_h  = df["high"].resample("1D").max()
    daily_l  = df["low"].resample("1D").min()
    # ffill weekends (Sat/Sun have NaN) so Monday bars inherit Friday's high/low
    daily_h = daily_h.ffill()
    daily_l = daily_l.ffill()
    # shift(1): daily_h[D] → pdh used for bars on day D+1
    pdh_s = daily_h.shift(1)
    pdl_s = daily_l.shift(1)
    # align back: each bar gets the PDH of its own calendar day
    df["pdh"] = pdh_s.reindex(date_idx).values
    df["pdl"] = pdl_s.reindex(date_idx).values

    # ── HTF trend (H1 EMA-50 slope) ───────────────────────────────────────────
    h1_close = df["close"].resample("1h").last().dropna()
    ema50     = h1_close.ewm(span=50, adjust=False).mean()
    # True = EMA rising (bullish), False = EMA flat/falling (bearish)
    h1_bull   = ema50 >= ema50.shift(1)
    htf_raw   = h1_bull.reindex(df.index, method="ffill")
    df["htf_trend"] = htf_raw.map({True: "bullish", False: "bearish"})

    return df


# ── pivot_swings ──────────────────────────────────────────────────────────────

def pivot_swings(df: pd.DataFrame, lookback: int = 12) -> pd.DataFrame:
    """
    Add rolling pivot high/low levels (most recent swing) with no look-ahead.

    pivot_high_level[i] = max(high[i-lookback : i])   (prior bars only)
    pivot_low_level[i]  = min(low[i-lookback  : i])

    Used by the optimizer's MSS check:
      long  MSS: close > pivot_high_level  (price broke above recent swing high)
      short MSS: close < pivot_low_level   (price broke below recent swing low)
    """
    df = df.copy()
    df["pivot_high_level"] = (
        df["high"].rolling(lookback, min_periods=3).max().shift(1)
    )
    df["pivot_low_level"] = (
        df["low"].rolling(lookback, min_periods=3).min().shift(1)
    )
    return df


# ── data preparation ──────────────────────────────────────────────────────────

def _load_m15(symbol: str) -> pd.DataFrame:
    fname = _SYMBOL_FILE[symbol]
    raw   = pd.read_csv(_HIST_DIR / fname)
    raw["timestamp"] = pd.to_datetime(raw["time"], utc=True)
    raw = (
        raw.set_index("timestamp")
           [["open", "high", "low", "close"]]
           .sort_index()
    )
    raw["spread"] = _SYNTH_SPREAD[symbol]
    return raw


def prepare_data(
    symbols: list[str] | None = None,
    start: str = _DATE_START,
    end: str   = _DATE_END,
    force: bool = False,
) -> None:
    """
    Build {SYMBOL}_5m_{start}_{end}.csv files in OUTDIR from M15 historical data.
    Files are named with '_5m_' to match the pattern expected by optimize_d2_rules.py.
    Idempotent — skips existing files unless force=True.
    """
    if symbols is None:
        symbols = list(_SYMBOL_FILE.keys())

    for sym in symbols:
        out_path = OUTDIR / f"{sym}_5m_{start}_{end}.csv"
        if out_path.exists() and not force:
            print(f"[prepare_data] {sym}: already exists → {out_path}")
            continue

        print(f"[prepare_data] {sym}: loading M15 data …")
        df = _load_m15(sym)
        mask = (df.index >= pd.Timestamp(start, tz="UTC")) & (
                df.index <= pd.Timestamp(end,   tz="UTC") + pd.Timedelta(days=1))
        df = df.loc[mask].copy()

        if len(df) < 100:
            print(f"[prepare_data] {sym}: WARNING — only {len(df)} bars in range")
        else:
            print(f"[prepare_data] {sym}: {len(df)} bars ({df.index[0]} … {df.index[-1]})")

        df.index.name = "timestamp"
        df.to_csv(out_path)
        print(f"[prepare_data] {sym}: saved → {out_path}")


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    prepare_data(force=False)
    print("Done. CSV files are in:", OUTDIR)
