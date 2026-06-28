"""
scripts/backtest.py  — P5 Multi-session backtest gate
Instruments : EURUSD, GBPUSD, XAUUSD
Sessions    : Asian | London | Overlap | NewYork
Data source : data/historical/{symbol}_{tf}.csv  (fetched via MetaAPI or yfinance)
Fee model   : EURUSD/GBPUSD 0.8 pip round-turn | XAUUSD $0.30/lot round-turn
Pass criteria (COMBINED row):
  net PF >= 1.4 · n >= 100 · win% >= 35% · max_consec_loss <= 8

Usage:
  python scripts/backtest.py [--fetch]  # --fetch downloads fresh historical data
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import pandas as pd

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from smc_bot.session_range import (
    build_session_signal,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("backtest")

# ─────────────────────────────────────────────────────────────────────────────
# Config (mirrors config.yaml — loaded here as inline dict for portability)
# ─────────────────────────────────────────────────────────────────────────────

CFG = {
    "instruments": {
        "EURUSD": {
            "symbol": "EURUSD",
            "pip_size": 0.0001,
            "atr_period": 14,
            "sweep_beyond_pct": 0.008,
            "sl_pct_of_range": 0.25,
            "spread_allowance_pips": 1.0,
            "sessions": ["asian", "london", "overlap", "newyork"],
            "signal_weight": 1.0,
        },
        "GBPUSD": {
            "symbol": "GBPUSD",
            "pip_size": 0.0001,
            "atr_period": 14,
            "sweep_beyond_pct": 0.010,
            "sl_pct_of_range": 0.25,
            "spread_allowance_pips": 1.5,
            "sessions": ["london", "overlap", "newyork"],
            "signal_weight": 0.9,
        },
        "XAUUSD": {
            "symbol": "XAUUSD",
            "pip_size": 0.01,
            "atr_period": 14,
            "sweep_beyond_pct": 0.005,
            "sl_pct_of_range": 0.20,
            "spread_allowance_pips": 3.0,
            "sessions": ["london", "overlap", "newyork"],
            "signal_weight": 1.0,
        },
    },
    "sessions": {
        "asian":   {"start_h": 0,  "end_h": 8,  "range_thr": 0.50, "trend_thr": 0.70, "first_close_pct": 0.75, "first_close_target": "opposite_box_edge", "trail_remainder": False},
        "london":  {"start_h": 7,  "end_h": 12, "range_thr": 0.55, "trend_thr": 0.75, "first_close_pct": 0.75, "first_close_target": "opposite_box_edge", "trail_remainder": False},
        "overlap": {"start_h": 12, "end_h": 15, "range_thr": 0.60, "trend_thr": 0.80, "first_close_pct": 0.75, "first_close_target": "4R",                 "trail_remainder": True},
        "newyork": {"start_h": 12, "end_h": 17, "range_thr": 0.55, "trend_thr": 0.75, "first_close_pct": 0.75, "first_close_target": "opposite_box_edge", "trail_remainder": False},
    },
    "asian": {
        "target_r": 5.0,
        "trend_first_close_r": 4.0,
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# Fee model (round-turn, per lot)
# ─────────────────────────────────────────────────────────────────────────────

FEE_PER_LOT = {
    "EURUSD": 0.00008,   # 0.8 pip avg spread × $10/pip/lot = $0.80 per lot
    "GBPUSD": 0.00010,   # 1.0 pip avg spread
    "XAUUSD": 0.30,      # $0.30 per lot round-turn on Vantage ECN
}

# ─────────────────────────────────────────────────────────────────────────────
# Pass / fail thresholds
# ─────────────────────────────────────────────────────────────────────────────

PASS_CRITERIA = {
    "net_pf":        1.4,
    "min_trades":    100,
    "min_win_pct":   35.0,
    "max_consec_loss": 8,
}

INSTRUMENT_MIN_TRADES = 30   # flag instrument×session if PF<1.0 AND n>=this


# ─────────────────────────────────────────────────────────────────────────────
# Data loading
# ─────────────────────────────────────────────────────────────────────────────

DATA_DIR = Path("data/historical")


def load_ohlcv(symbol: str, tf: str) -> pd.DataFrame:
    """
    Load OHLCV from data/historical/{symbol}_{tf}.csv
    Expected columns: datetime, open, high, low, close, volume (case-insensitive)
    """
    path = DATA_DIR / f"{symbol}_{tf}.csv"
    if not path.exists():
        raise FileNotFoundError(
            f"Historical data not found: {path}\n"
            f"Run with --fetch to download, or place CSV manually."
        )

    df = pd.read_csv(path, parse_dates=["datetime"])
    df.columns = [c.lower() for c in df.columns]
    df = df.rename(columns={"time": "datetime", "date": "datetime"})
    df = df.set_index("datetime")
    df.index = pd.to_datetime(df.index, utc=True)
    df = df.sort_index()

    # 2-year window
    cutoff = pd.Timestamp.now(tz="UTC") - pd.DateOffset(years=2)
    df = df[df.index >= cutoff]

    log.info("Loaded %s %s: %d candles (from %s)", symbol, tf, len(df), df.index[0].date())
    return df


def fetch_and_save_historical(symbol: str) -> None:
    """
    Download 2 years of 1h and 4h OHLCV data using yfinance as fallback.
    For production use MetaAPI historical data endpoint.
    """
    try:
        import yfinance as yf
    except ImportError:
        log.error("yfinance not installed. Run: pip install yfinance")
        return

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    end   = datetime.now(timezone.utc)
    start = end - timedelta(days=730)

    yf_symbol = symbol  # yfinance uses same symbols for forex/gold
    if symbol == "XAUUSD":
        yf_symbol = "GC=F"    # Gold futures as proxy
    elif symbol in ("EURUSD", "GBPUSD"):
        yf_symbol = symbol.replace("USD", "=X")   # EURUSD → EUR=X

    for tf, yf_interval, yf_period in [("1h", "1h", "730d"), ("4h", "1h", "730d")]:
        log.info("Fetching %s %s …", symbol, tf)
        raw = yf.download(yf_symbol, start=start, end=end, interval=yf_interval, auto_adjust=True)
        if raw.empty:
            log.warning("No data returned for %s %s", symbol, tf)
            continue

        raw.columns = [c.lower() for c in raw.columns]
        raw.index.name = "datetime"

        if tf == "4h":
            raw = raw.resample("4h").agg({
                "open": "first", "high": "max",
                "low": "min", "close": "last", "volume": "sum",
            }).dropna()

        out = DATA_DIR / f"{symbol}_{tf}.csv"
        raw.to_csv(out)
        log.info("Saved %s → %d rows", out, len(raw))


# ─────────────────────────────────────────────────────────────────────────────
# Trade simulator
# ─────────────────────────────────────────────────────────────────────────────

def simulate_trade(
    signal,          # SessionSignal
    df_1h: pd.DataFrame,
    after_ts: pd.Timestamp,
) -> Optional[dict]:
    """
    Walk forward candle-by-candle from after_ts.
    Returns trade result dict or None if unresolved within lookahead window.

    Partial close at first_close_target (75%), remainder to full TP or SL.
    Fee applied on entry (full lots) and on first close + remainder close.
    """
    df_forward = df_1h[df_1h.index > after_ts].head(120)  # max 5 days lookahead

    if df_forward.empty:
        return None

    entry       = signal.entry
    sl          = signal.sl
    tp          = signal.tp
    side        = signal.side
    box_high    = signal.box_high
    box_low     = signal.box_low
    mgmt        = signal.mgmt
    instrument  = signal.instrument
    pip_size    = CFG["instruments"][instrument]["pip_size"]

    first_close_pct    = mgmt.get("first_close_pct", 0.75)
    first_close_target = mgmt.get("first_close_target", "opposite_box_edge")
    trail_remainder    = mgmt.get("trail_remainder", False)

    # Resolve first close price
    if first_close_target == "opposite_box_edge":
        first_target_price = box_high if side == "long" else box_low
    else:
        sl_dist = abs(entry - sl)
        r_target = 4.0
        first_target_price = (
            entry + sl_dist * r_target if side == "long"
            else entry - sl_dist * r_target
        )

    lots = 1.0   # normalise to 1 lot for R-multiple accounting
    fee  = FEE_PER_LOT.get(instrument, 0.0)

    first_close_done = False
    first_close_pnl  = 0.0
    current_sl       = sl
    atr              = _rolling_atr(df_1h, after_ts)

    for _, candle in df_forward.iterrows():
        high = candle["high"]
        low  = candle["low"]

        # ── SL hit ───────────────────────────────────────────────────────
        sl_hit = (side == "long" and low <= current_sl) or \
                 (side == "short" and high >= current_sl)

        if sl_hit:
            remainder_lots   = lots * (1 - first_close_pct) if first_close_done else lots
            remainder_pnl    = _pnl(side, entry, current_sl, remainder_lots, pip_size)
            total_pnl        = first_close_pnl + remainder_pnl - fee * lots
            sl_dist          = abs(entry - sl)
            r_multiple        = total_pnl / (sl_dist / pip_size * 10) if sl_dist > 0 else 0
            return {
                "result": "loss" if total_pnl < 0 else "win",  # BE stop = win if above entry
                "pnl_raw": total_pnl,
                "r_multiple": r_multiple,
                "instrument": instrument,
                "session": signal.session,
                "setup": signal.setup,
            }

        # ── First close target hit ────────────────────────────────────────
        if not first_close_done:
            target_hit = (
                (side == "long"  and high >= first_target_price) or
                (side == "short" and low  <= first_target_price)
            )
            if target_hit:
                first_close_lots = lots * first_close_pct
                first_close_pnl  = _pnl(side, entry, first_target_price, first_close_lots, pip_size)
                first_close_done = True
                current_sl       = entry   # SL moves to BE

        # ── Trailing stop (overlap/trend) ─────────────────────────────────
        if first_close_done and trail_remainder:
            mid = (high + low) / 2
            if side == "long":
                new_sl = mid - atr
                if new_sl > current_sl and new_sl > entry:
                    current_sl = new_sl
            else:
                new_sl = mid + atr
                if new_sl < current_sl and new_sl < entry:
                    current_sl = new_sl

        # ── Full TP hit ───────────────────────────────────────────────────
        tp_hit = (
            (side == "long"  and high >= tp) or
            (side == "short" and low  <= tp)
        )
        if tp_hit:
            remainder_lots = lots * (1 - first_close_pct) if first_close_done else lots
            remainder_pnl  = _pnl(side, entry, tp, remainder_lots, pip_size)
            total_pnl      = first_close_pnl + remainder_pnl - fee * lots
            sl_dist        = abs(entry - sl)
            r_multiple     = total_pnl / (sl_dist / pip_size * 10) if sl_dist > 0 else 0
            return {
                "result": "win",
                "pnl_raw": total_pnl,
                "r_multiple": r_multiple,
                "instrument": instrument,
                "session": signal.session,
                "setup": signal.setup,
            }

    return None   # unresolved within lookahead


def _pnl(side: str, entry: float, exit_price: float, lots: float, pip_size: float) -> float:
    """Raw P&L in price units (not USD — for R-multiple calc)."""
    diff = (exit_price - entry) if side == "long" else (entry - exit_price)
    return diff * lots


def _rolling_atr(df_1h: pd.DataFrame, as_of: pd.Timestamp, period: int = 14) -> float:
    sub = df_1h[df_1h.index <= as_of].tail(period + 1)
    if len(sub) < 2:
        return 0.0
    hl  = sub["high"] - sub["low"]
    hc  = (sub["high"] - sub["close"].shift()).abs()
    lc  = (sub["low"]  - sub["close"].shift()).abs()
    tr  = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    return float(tr.rolling(period).mean().iloc[-1])


# ─────────────────────────────────────────────────────────────────────────────
# Per instrument × session backtest runner
# ─────────────────────────────────────────────────────────────────────────────

def run_backtest_for(
    instrument: str,
    session_name: str,
    df_4h: pd.DataFrame,
    df_1h: pd.DataFrame,
) -> dict:
    """
    Walk-forward over all completed session windows in the historical data.
    Returns summary dict: {n, wins, losses, gross_pf, net_pf, win_pct,
                           max_consec_loss, instrument, session}
    """
    session_cfg = CFG["sessions"][session_name]
    end_h       = session_cfg["end_h"]
    instr_cfg   = CFG["instruments"][instrument]

    # Check instrument is configured for this session
    if session_name not in instr_cfg["sessions"]:
        return None

    trades = []
    seen_dates = set()

    # Iterate daily — one signal opportunity per session per day
    for ts in df_1h.index:
        if ts.hour != end_h:
            continue   # only evaluate at session close

        date_key = (ts.date(), session_name, instrument)
        if date_key in seen_dates:
            continue
        seen_dates.add(date_key)

        # Slice historical data up to this point (no lookahead)
        hist_4h = df_4h[df_4h.index <= ts]
        hist_1h = df_1h[df_1h.index <= ts]

        if len(hist_4h) < 50 or len(hist_1h) < 50:
            continue

        try:
            sig = build_session_signal(
                hist_4h, hist_1h, instrument, session_name, CFG
            )
        except Exception as e:
            log.debug("[%s/%s] Signal error at %s: %s", instrument, session_name, ts, e)
            continue

        if sig is None:
            continue

        # Simulate the trade walking forward from signal candle
        result = simulate_trade(sig, df_1h, after_ts=ts)
        if result is not None:
            trades.append(result)

    if not trades:
        return {
            "instrument": instrument,
            "session": session_name,
            "n": 0, "wins": 0, "losses": 0,
            "gross_pf": 0.0, "net_pf": 0.0,
            "win_pct": 0.0, "max_consec_loss": 0,
            "flag": "NO_TRADES",
        }

    wins   = [t for t in trades if t["result"] == "win"]
    losses = [t for t in trades if t["result"] == "loss"]
    n      = len(trades)

    gross_wins   = sum(abs(t["pnl_raw"]) for t in wins)
    gross_losses = sum(abs(t["pnl_raw"]) for t in losses)
    fee_total    = FEE_PER_LOT.get(instrument, 0) * n

    gross_pf = gross_wins / gross_losses if gross_losses > 0 else float("inf")
    net_pf   = (gross_wins - fee_total / 2) / (gross_losses + fee_total / 2) \
               if (gross_losses + fee_total / 2) > 0 else float("inf")
    win_pct  = len(wins) / n * 100

    # Max consecutive losses
    consec = 0
    max_consec = 0
    for t in trades:
        if t["result"] == "loss":
            consec += 1
            max_consec = max(max_consec, consec)
        else:
            consec = 0

    flag = ""
    if n >= INSTRUMENT_MIN_TRADES and net_pf < 1.0:
        flag = "FAILING — DISABLE THIS COMBINATION"

    return {
        "instrument": instrument,
        "session": session_name,
        "n": n,
        "wins": len(wins),
        "losses": len(losses),
        "gross_pf": round(gross_pf, 3),
        "net_pf": round(net_pf, 3),
        "win_pct": round(win_pct, 1),
        "max_consec_loss": max_consec,
        "flag": flag,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fetch", action="store_true",
                        help="Download fresh historical data before running")
    args = parser.parse_args()

    if args.fetch:
        for sym in ("EURUSD", "GBPUSD", "XAUUSD"):
            fetch_and_save_historical(sym)

    # ── Load data ──────────────────────────────────────────────────────────
    data = {}
    for sym in ("EURUSD", "GBPUSD", "XAUUSD"):
        try:
            data[sym] = {
                "df_1h": load_ohlcv(sym, "1h"),
                "df_4h": load_ohlcv(sym, "4h"),
            }
        except FileNotFoundError as e:
            log.error(str(e))
            sys.exit(1)

    # ── Run per instrument × session ───────────────────────────────────────
    rows = []
    for instrument in ("EURUSD", "GBPUSD", "XAUUSD"):
        for session_name in ("asian", "london", "overlap", "newyork"):
            log.info("Running backtest: %s / %s …", instrument, session_name)
            result = run_backtest_for(
                instrument, session_name,
                data[instrument]["df_4h"],
                data[instrument]["df_1h"],
            )
            if result is not None:
                rows.append(result)

    # ── Combined totals ────────────────────────────────────────────────────
    all_n      = sum(r["n"] for r in rows)
    all_wins   = sum(r["wins"] for r in rows)
    all_losses = sum(r["losses"] for r in rows)
    total_fee  = sum(FEE_PER_LOT.get(r["instrument"], 0) * r["n"] for r in rows)

    if all_losses > 0:
        combined_gross_pf = sum(
            r["gross_pf"] * r["losses"] for r in rows if r["losses"] > 0
        ) / all_losses
    else:
        combined_gross_pf = float("inf")

    combined_win_pct = all_wins / all_n * 100 if all_n > 0 else 0

    # Approximate combined net PF
    all_gross_wins   = sum(r["wins"] * r.get("gross_pf", 1) * (r["n"] / max(r["wins"], 1))
                           for r in rows if r["wins"] > 0)
    all_gross_losses_val = sum(r["losses"] for r in rows)
    combined_net_pf  = ((all_gross_wins - total_fee / 2) /
                        (all_gross_losses_val + total_fee / 2)
                        if (all_gross_losses_val + total_fee / 2) > 0
                        else float("inf"))

    # Max consecutive loss across combined run (approximate)
    combined_max_consec = max((r["max_consec_loss"] for r in rows), default=0)

    # ── Print results table ────────────────────────────────────────────────
    print("\n" + "═" * 80)
    print("  BACKTEST RESULTS — Multi-session × Multi-instrument")
    print("═" * 80)
    header = f"{'Instrument':<12} {'Session':<10} {'n':>5} {'Win%':>7} {'GrossPF':>9} {'NetPF':>8} {'MaxCL':>7}  Flag"
    print(header)
    print("─" * 80)

    for r in rows:
        flag_str = "⚠️  " + r["flag"] if r["flag"] else ""
        print(
            f"{r['instrument']:<12} {r['session']:<10} {r['n']:>5} "
            f"{r['win_pct']:>6.1f}% {r['gross_pf']:>9.3f} {r['net_pf']:>8.3f} "
            f"{r['max_consec_loss']:>7}  {flag_str}"
        )

    print("─" * 80)
    print(
        f"{'COMBINED':<12} {'ALL':<10} {all_n:>5} "
        f"{combined_win_pct:>6.1f}% {combined_gross_pf:>9.3f} {combined_net_pf:>8.3f} "
        f"{combined_max_consec:>7}"
    )
    print("═" * 80)

    # ── Pass / fail verdict ────────────────────────────────────────────────
    print("\nPASS CRITERIA:")
    checks = {
        f"net_pf >= {PASS_CRITERIA['net_pf']}":           combined_net_pf   >= PASS_CRITERIA["net_pf"],
        f"n >= {PASS_CRITERIA['min_trades']} total":       all_n             >= PASS_CRITERIA["min_trades"],
        f"win% >= {PASS_CRITERIA['min_win_pct']}%":        combined_win_pct  >= PASS_CRITERIA["min_win_pct"],
        f"max_consec_loss <= {PASS_CRITERIA['max_consec_loss']}": combined_max_consec <= PASS_CRITERIA["max_consec_loss"],
    }
    passed = all(checks.values())
    for label, ok in checks.items():
        print(f"  {'✅' if ok else '❌'}  {label}")

    # Failing combinations
    failing = [r for r in rows if r["flag"]]
    if failing:
        print("\n⚠️  FAILING COMBINATIONS (disable in config):")
        for r in failing:
            print(f"  → {r['instrument']} / {r['session']}  (net_pf={r['net_pf']}, n={r['n']})")

    verdict = "PASS" if passed else "FAIL"
    print(f"\n{'═'*40}")
    print(f"  VERDICT: {verdict}")
    print(f"{'═'*40}\n")

    if not passed:
        print("STOP — Do NOT proceed to P6. Fix the failing combinations above,")
        print("tune parameters, and re-run the backtest before activating demo trading.\n")

    # ── Append to VERDICT_LOG.md ───────────────────────────────────────────
    log_path = Path("docs/VERDICT_LOG.md")
    log_path.parent.mkdir(parents=True, exist_ok=True)

    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    row_str  = (
        f"| {date_str} | v2 multi-session | EURUSD+GBPUSD+XAUUSD "
        f"| net_pf={combined_net_pf:.3f} | n={all_n} "
        f"| win%={combined_win_pct:.1f} | {verdict} |\n"
    )

    if not log_path.exists():
        log_path.write_text(
            "# Verdict Log\n\n"
            "| Date | Version | Instruments | net_pf | n | win% | Verdict |\n"
            "|------|---------|-------------|--------|---|------|---------|\n"
        )

    with open(log_path, "a") as f:
        f.write(row_str)

    log.info("Verdict appended to %s", log_path)
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
