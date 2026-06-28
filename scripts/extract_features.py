"""
SMC feature extraction — sweeps, sessions, CHoCH, BOS, FVG.

Reads processed OHLCV Parquet (M15 + H4), runs ST-A2 signal chain in debug mode,
extracts SMC events, writes feature Parquet to data/features/{type}/{SYMBOL}.parquet.

Usage:
    python scripts/extract_features.py --symbols EURUSD GBPUSD
    python scripts/extract_features.py --symbols EURUSD --start 2021-01 --end 2022-12

Outputs:
    data/features/sweeps/{sym}.parquet
    data/features/sessions/{sym}.parquet
    data/features/fvg/{sym}.parquet
"""

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DATA_PROC = ROOT / "data" / "processed"
DATA_FEAT = ROOT / "data" / "features"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("extract")


def _load_parquet_as_bars(sym: str, tf: str) -> list[dict]:
    path = DATA_PROC / sym / f"{tf}.parquet"
    if not path.exists():
        log.error("Missing %s — run build_timeframes.py first", path)
        return []
    df = pd.read_parquet(path)
    if df.empty:
        return []
    df["time"] = pd.to_datetime(df["timestamp_utc"], utc=True).dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return df[["time", "open", "high", "low", "close", "volume"]].to_dict("records")


def _load_csv_as_bars(sym: str, tf: str) -> list[dict]:
    """Fallback: load from existing CSV if Parquet not yet built."""
    csv_sym = sym.replace("USD", "_USD").replace("GBPUSD", "GBP_USD").replace("EURUSD", "EUR_USD")
    path = ROOT / "data" / "historical" / f"{csv_sym}_{tf}.csv"
    if not path.exists():
        return []
    df = pd.read_csv(path)
    df.columns = [c.lower() for c in df.columns]
    return df[["time", "open", "high", "low", "close", "volume"]].to_dict("records")


def _bars_for(sym: str, tf: str) -> list[dict]:
    bars = _load_parquet_as_bars(sym, tf)
    if not bars:
        log.warning("%s %s: Parquet not found, falling back to CSV", sym, tf)
        bars = _load_csv_as_bars(sym, tf)
    return bars


def extract_sessions_and_sweeps(sym: str, start_dt=None, end_dt=None) -> tuple[list, list]:
    from strategy.session_liquidity.session_strategy import run_strategy

    m15_bars = _bars_for(sym, "M15")
    h4_bars  = _bars_for(sym, "H4")

    if not m15_bars or not h4_bars:
        log.error("%s: no bars available for extraction", sym)
        return [], []

    if start_dt:
        m15_bars = [b for b in m15_bars if b["time"] >= start_dt]
        h4_bars  = [b for b in h4_bars  if b["time"] >= start_dt]
    if end_dt:
        m15_bars = [b for b in m15_bars if b["time"] <= end_dt]
        h4_bars  = [b for b in h4_bars  if b["time"] <= end_dt]

    log.info("%s: running signal chain on %d M15 bars + %d H4 bars", sym, len(m15_bars), len(h4_bars))

    try:
        signals, debug_records = run_strategy(m15_bars, h4_bars, sym, debug=True)
    except TypeError:
        signals = run_strategy(m15_bars, h4_bars, sym)
        debug_records = []

    log.info("%s: %d signals, %d debug records", sym, len(signals), len(debug_records))

    sweep_events = []
    session_events = []

    for rec in debug_records:
        if rec.get("event") == "sweep":
            sweep_events.append({
                "timestamp_utc": rec.get("time"),
                "session": rec.get("session", ""),
                "direction": rec.get("direction", ""),
                "sweep_level": rec.get("sweep_level", float("nan")),
                "sweep_close": rec.get("close", float("nan")),
                "session_high": rec.get("session_high", float("nan")),
                "session_low": rec.get("session_low", float("nan")),
                "htf_bias": rec.get("htf_bias", ""),
            })
        elif rec.get("event") == "session":
            session_events.append({
                "session_open": rec.get("session_open"),
                "session_close": rec.get("session_close"),
                "session": rec.get("session", ""),
                "session_high": rec.get("session_high", float("nan")),
                "session_low": rec.get("session_low", float("nan")),
                "session_mid": rec.get("session_mid", float("nan")),
                "range_pips": rec.get("range_pips", float("nan")),
                "session_type": rec.get("session_type", ""),
            })

    for sig in signals:
        sweep_events.append({
            "timestamp_utc": getattr(sig, "entry_time", None) or getattr(sig, "time", None),
            "session": getattr(sig, "session", ""),
            "direction": getattr(sig, "direction", ""),
            "sweep_level": getattr(sig, "sweep_level", float("nan")),
            "sweep_close": getattr(sig, "entry", float("nan")),
            "session_high": float("nan"),
            "session_low": float("nan"),
            "htf_bias": getattr(sig, "htf_bias", ""),
        })

    return session_events, sweep_events


def extract_fvg(sym: str, start_dt=None, end_dt=None) -> list:
    """Scan M15 bars for FVG (3-candle displacement pattern)."""
    m15_bars = _bars_for(sym, "M15")
    if not m15_bars:
        return []

    if start_dt:
        m15_bars = [b for b in m15_bars if b["time"] >= start_dt]
    if end_dt:
        m15_bars = [b for b in m15_bars if b["time"] <= end_dt]

    try:
        from session_smc.fvg import find_fvgs
        fvgs = find_fvgs(m15_bars)
        log.info("%s: %d FVG events extracted", sym, len(fvgs))
        return fvgs
    except ImportError:
        log.warning("%s: session_smc.fvg not importable, skipping FVG extraction", sym)
        return []


def _write_feature(events: list, schema_cols: list, out_path: Path):
    if not events:
        log.warning("No events to write to %s", out_path)
        return
    df = pd.DataFrame(events, columns=schema_cols)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path, index=False, compression="snappy")
    log.info("Wrote %d events → %s", len(df), out_path)


SWEEP_COLS   = ["timestamp_utc", "session", "direction", "sweep_level", "sweep_close",
                "session_high", "session_low", "htf_bias"]
SESSION_COLS = ["session_open", "session_close", "session", "session_high", "session_low",
                "session_mid", "range_pips", "session_type"]
FVG_COLS     = ["timestamp_utc", "direction", "fvg_high", "fvg_low", "fvg_mid", "atr_mult", "filled"]


def main():
    parser = argparse.ArgumentParser(description="Extract SMC features from processed OHLCV")
    parser.add_argument("--symbols", nargs="+", default=["EURUSD", "GBPUSD"])
    parser.add_argument("--start", help="Start datetime prefix e.g. 2021-01-01T00:00:00Z")
    parser.add_argument("--end",   help="End datetime prefix e.g. 2022-12-31T23:59:59Z")
    args = parser.parse_args()

    for sym in args.symbols:
        log.info("=== Extracting features for %s ===", sym)

        session_events, sweep_events = extract_sessions_and_sweeps(sym, args.start, args.end)
        _write_feature(session_events, SESSION_COLS, DATA_FEAT / "sessions" / f"{sym}.parquet")
        _write_feature(sweep_events,   SWEEP_COLS,   DATA_FEAT / "sweeps"   / f"{sym}.parquet")

        fvg_events = extract_fvg(sym, args.start, args.end)
        if fvg_events:
            _write_feature(fvg_events, FVG_COLS, DATA_FEAT / "fvg" / f"{sym}.parquet")

    log.info("Feature extraction complete.")


if __name__ == "__main__":
    main()
