"""
6-month historical replay — ST-A2 baseline vs D2-combined.
Date range: 2026-01-01 to 2026-06-19.

BASELINE replicates ST-A2:
  4H bias → Asian range → sweep → displacement → entry at displacement close
  SL = sweep wick ± 2pip | min_sl_pips=5.0 | TP=3R

D2_COMBINED adds three context gates on top of the same execution chain:
  Gate A (d2_structure): 1D swing structure (from H4) must agree with 4H bias
  Gate B (d2_location):  session bar open must be in discount (long) / premium (short)
                         vs PDH/PDL midpoint
  Gate C (d2_poi):       swept level must be within 30 pips of PDL (long) or PDH (short)

Uses strategy/session_liquidity/ components — same code that produced ST-A2.

Usage:
    python3 scripts/replay_6m.py
    python3 scripts/replay_6m.py --symbols EURUSD --start 2025-07-01
    python3 scripts/replay_6m.py --parquet --symbols EURUSD --start 2024-11-01 --end 2024-11-30
"""

from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from strategy.session_liquidity.session_builder import (
    build_asian_range,
    classify_session,
)
from strategy.session_liquidity.bias_filter import htf_bias
from strategy.session_liquidity.sweep_detector import detect_sweep
from strategy.session_liquidity.displacement_detector import (
    detect_displacement,
    wilder_atr,
)
from strategy.session_liquidity.entry_engine import build_signal

from session_smc.daily_bias import build_daily_context, classify_location

# ── Cost model ────────────────────────────────────────────────────────────────

COSTS = {
    "EURUSD": {"standard": 1.4, "stress2x": 2.8},
    "GBPUSD": {"standard": 1.8, "stress2x": 3.6},
}
PIP = 0.0001

DATA_DIR = Path(__file__).parent.parent / "data" / "historical"
DATA_PROC = Path(__file__).parent.parent / "data" / "processed"
OUT_DIR = Path(__file__).parent.parent / "docs"
RPT_DIR = Path(__file__).parent.parent / "reports"

_UTC = timezone.utc


# ── Config (mirrors ST-A2) ────────────────────────────────────────────────────

ST_A2_CONFIG = {
    "rr": 3.0,
    "sl_buffer_pips": 2.0,
    "displacement_mult": 1.2,
    "atr_period": 14,
    "sweep_timeout_bars": 4,
    "min_sl_pips": 5.0,
    "min_range_pips": {
        "EURUSD": 15.0,
        "GBPUSD": 20.0,
    },
    # D2 gates — toggled per variant
    "d2_structure_gate": False,
    "d2_location_gate": False,
    "d2_poi_gate": False,
    "d2_poi_pips": 30.0,
}

D2_CONFIG = {
    **ST_A2_CONFIG,
    "d2_structure_gate": True,
    "d2_location_gate": True,
    "d2_poi_gate": True,
}


# ── Trade dataclass ────────────────────────────────────────────────────────────


@dataclass
class Trade:
    variant: str
    symbol: str
    session: str
    direction: str
    entry: float
    sl: float
    tp1: float
    sl_pips: float
    entry_time: str
    exit_price: float = 0.0
    exit_time: str = ""
    exit_reason: str = ""
    gross_r: float = 0.0
    net_r_std: float = 0.0
    net_r_2x: float = 0.0


# ── CSV helpers ───────────────────────────────────────────────────────────────


def load_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path) as f:
        return [
            {
                "time": row["time"],
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
            }
            for row in csv.DictReader(f)
        ]


def filter_range(candles: list[dict], start: str, end: str) -> list[dict]:
    return [c for c in candles if start <= c["time"] <= end]


def load_parquet(
    symbol: str, tf: str, start: str | None = None, end: str | None = None
) -> list[dict]:
    try:
        import pandas as pd
    except ImportError:
        print("pandas required for --parquet mode: pip install pandas pyarrow")
        sys.exit(1)

    path = DATA_PROC / symbol / f"{tf}.parquet"
    if not path.exists():
        print(f"[{symbol}] Parquet not found: {path}")
        return []

    df = pd.read_parquet(
        path, columns=["timestamp_utc", "open", "high", "low", "close"]
    )
    df["time"] = pd.to_datetime(df["timestamp_utc"], utc=True).dt.strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    df = df.sort_values("time")

    if start:
        s = start if "T" in start else start + "T00:00:00Z"
        df = df[df["time"] >= s]
    if end:
        e = end if "T" in end else end + "T23:59:59Z"
        df = df[df["time"] <= e]

    return df[["time", "open", "high", "low", "close"]].to_dict("records")


def _utc(t) -> datetime:
    if isinstance(t, datetime):
        return t if t.tzinfo else t.replace(tzinfo=_UTC)
    return datetime.fromisoformat(str(t).replace("Z", "+00:00"))


# ── Trade simulation ──────────────────────────────────────────────────────────


def simulate_trade(
    sig,
    day_bars: list[tuple[dict, str]],
    disp_bar_idx_in_day: int,
    symbol: str,
    session: str,
    variant: str,
) -> "Trade | None":
    """Simulate SL/TP/timeout exit from displacement bar onward within the day."""
    if sig is None:
        return None

    entry_price = sig.entry
    cost_std = COSTS.get(symbol, {}).get("standard", 1.4)
    cost_2x = COSTS.get(symbol, {}).get("stress2x", 2.8)
    entry_time = day_bars[disp_bar_idx_in_day][0]["time"]

    t = Trade(
        variant=variant,
        symbol=symbol,
        session=session,
        direction=sig.side,
        entry=entry_price,
        sl=sig.stop_loss,
        tp1=sig.take_profit,
        sl_pips=sig.risk_pips,
        entry_time=entry_time,
    )

    is_long = sig.side == "long"

    for j in range(disp_bar_idx_in_day + 1, len(day_bars)):
        bar, sess = day_bars[j]

        if is_long:
            if bar["low"] <= sig.stop_loss:
                t.exit_price, t.exit_reason, t.exit_time = (
                    sig.stop_loss,
                    "SL",
                    bar["time"],
                )
                break
            if bar["high"] >= sig.take_profit:
                t.exit_price, t.exit_reason, t.exit_time = (
                    sig.take_profit,
                    "TP1",
                    bar["time"],
                )
                break
        else:
            if bar["high"] >= sig.stop_loss:
                t.exit_price, t.exit_reason, t.exit_time = (
                    sig.stop_loss,
                    "SL",
                    bar["time"],
                )
                break
            if bar["low"] <= sig.take_profit:
                t.exit_price, t.exit_reason, t.exit_time = (
                    sig.take_profit,
                    "TP1",
                    bar["time"],
                )
                break
    else:
        last = day_bars[-1][0]
        t.exit_price, t.exit_reason, t.exit_time = (
            last["close"],
            "SESSION_END",
            last["time"],
        )

    if not t.exit_time:
        last = day_bars[-1][0]
        t.exit_price, t.exit_reason, t.exit_time = (
            last["close"],
            "SESSION_END",
            last["time"],
        )

    if sig.risk_pips <= 0:
        return None

    gross_pips = (
        (t.exit_price - entry_price) / PIP
        if is_long
        else (entry_price - t.exit_price) / PIP
    )
    t.gross_r = gross_pips / sig.risk_pips
    t.net_r_std = t.gross_r - cost_std / sig.risk_pips
    t.net_r_2x = t.gross_r - cost_2x / sig.risk_pips
    return t


# ── Core walk-forward ─────────────────────────────────────────────────────────


def run_variant(
    variant: str,
    symbol: str,
    candles_m15: list[dict],
    candles_4h: list[dict],
    cfg: dict,
) -> list[Trade]:
    """Walk-forward over 6-month M15 data; apply D2 gates if enabled."""
    sorted_m15 = sorted(candles_m15, key=lambda c: c["time"])
    sorted_4h = sorted(candles_4h, key=lambda c: c["time"])

    atrs = wilder_atr(sorted_m15, cfg["atr_period"])
    atr_map = {c["time"]: a for c, a in zip(sorted_m15, atrs)}

    min_range = float(
        cfg["min_range_pips"].get(symbol[:6].replace("_", "").upper(), 15.0)
    )

    # Pre-group killzone bars by UTC date
    kz_by_date: dict[date, list] = {}
    for c in sorted_m15:
        dt = _utc(c["time"])
        s = classify_session(dt)
        if s is not None:
            kz_by_date.setdefault(dt.date(), []).append((c, s))

    d2_on = (
        cfg.get("d2_structure_gate")
        or cfg.get("d2_location_gate")
        or cfg.get("d2_poi_gate")
    )

    trades: list[Trade] = []

    for trade_date in sorted(kz_by_date.keys()):

        # ── Asian range (reference for sweep detection) ───────────────────────
        asian = build_asian_range(sorted_m15, trade_date)
        if asian is None or asian.range_pips < min_range:
            continue

        # ── Day start for 4H bias (London open) ──────────────────────────────
        day_start_utc = datetime(
            trade_date.year, trade_date.month, trade_date.day, 7, 0, tzinfo=_UTC
        )
        bias = htf_bias(sorted_4h, day_start_utc)
        if bias == "neutral":
            continue

        # ── D2 Stage 0 — daily context ────────────────────────────────────────
        d2_ctx = None
        if d2_on:
            d2_ctx = build_daily_context(sorted_4h, day_start_utc)
            if d2_ctx is None:
                continue  # not enough daily history yet (first few days of data)

            # Gate A: daily structure must not conflict with 4H bias
            if cfg.get("d2_structure_gate"):
                ds = d2_ctx["structure"]
                if ds != "neutral" and ds != bias:
                    continue

        # ── Session loop ──────────────────────────────────────────────────────
        day_bars = kz_by_date[trade_date]
        session_traded: set = set()
        pending: "dict | None" = None

        for bar_idx, (candle, session) in enumerate(day_bars):
            if session in session_traded:
                continue

            # Drop pending when session changes
            if pending and pending["session"] != session:
                pending = None

            if pending is None:
                # ── D2 Gate B — premium/discount at this candle ───────────────
                if d2_on and d2_ctx is not None and cfg.get("d2_location_gate"):
                    loc = classify_location(
                        float(candle["open"]), d2_ctx["pdh"], d2_ctx["pdl"]
                    )
                    if bias == "bullish" and loc == "premium":
                        continue
                    if bias == "bearish" and loc == "discount":
                        continue

                sweep = detect_sweep(candle, asian.high, asian.low, bias)
                if sweep.detected:
                    # ── D2 Gate C — swept level near PDH/PDL ──────────────────
                    if d2_on and d2_ctx is not None and cfg.get("d2_poi_gate"):
                        poi_thr = cfg.get("d2_poi_pips", 30.0) * PIP
                        sp = sweep.sweep_price
                        if bias == "bullish" and abs(sp - d2_ctx["pdl"]) > poi_thr:
                            continue
                        if bias == "bearish" and abs(sp - d2_ctx["pdh"]) > poi_thr:
                            continue

                    pending = {"sweep": sweep, "bar_idx": bar_idx, "session": session}

            else:
                bars_since = bar_idx - pending["bar_idx"]
                if bars_since > cfg["sweep_timeout_bars"]:
                    pending = None
                    continue

                atr_val = atr_map.get(candle["time"])
                disp = detect_displacement(
                    candle, atr_val, pending["sweep"].side, cfg["displacement_mult"]
                )

                if disp.detected:
                    sig = build_signal(
                        candle,
                        pending["sweep"],
                        disp,
                        asian,
                        session,
                        cfg["rr"],
                        cfg["sl_buffer_pips"],
                    )
                    pending = None

                    if sig is None:
                        continue
                    if sig.risk_pips < cfg.get("min_sl_pips", 0.0):
                        continue

                    trade = simulate_trade(
                        sig, day_bars, bar_idx, symbol, session, variant
                    )
                    if trade is not None:
                        trades.append(trade)
                        session_traded.add(session)

    return trades


# ── Metrics ───────────────────────────────────────────────────────────────────


def metrics(trades: list[Trade], r_field: str) -> dict:
    if not trades:
        return {"n": 0, "pf": 0.0, "wr": 0.0, "avg_r": 0.0, "max_dd": 0.0}
    vals = [getattr(t, r_field) for t in trades]
    wins = sum(1 for v in vals if v > 0)
    g_win = sum(v for v in vals if v > 0)
    g_loss = abs(sum(v for v in vals if v <= 0))
    pf = g_win / g_loss if g_loss > 0 else float("inf")
    equity = peak = max_dd = 0.0
    for v in vals:
        equity += v
        if equity > peak:
            peak = equity
        dd = peak - equity
        if dd > max_dd:
            max_dd = dd
    return {
        "n": len(trades),
        "pf": round(pf, 3),
        "wr": round(wins / len(trades) * 100, 1),
        "avg_r": round(sum(vals) / len(trades), 3),
        "max_dd": round(max_dd, 2),
    }


# ── Reports ───────────────────────────────────────────────────────────────────


def monthly_breakdown(trades: list[Trade], r_field: str) -> None:
    by_month: dict[str, list[Trade]] = {}
    for t in trades:
        m = t.entry_time[:7]
        by_month.setdefault(m, []).append(t)

    print(f"\n  {'Month':<10} {'n':>4} {'PF':>7} {'WR%':>6} {'AvgR':>7} {'MaxDD':>7}")
    print(f"  {'─' * 46}")
    for month in sorted(by_month):
        m = metrics(by_month[month], r_field)
        flag = " ⚠" if m["pf"] < 1.0 and m["n"] >= 3 else ""
        print(
            f"  {month:<10} {m['n']:>4} {m['pf']:>7.3f} {m['wr']:>5.1f}% "
            f"{m['avg_r']:>7.3f} {m['max_dd']:>7.2f}{flag}"
        )


def print_report(variant: str, symbol: str, trades: list[Trade]) -> None:
    std = metrics(trades, "net_r_std")
    s2x = metrics(trades, "net_r_2x")
    gate = ""
    if std["n"] >= 10:
        ok = std["pf"] > 1.0 and s2x["pf"] > 1.0
        gate = "  Gate (PF>1.0 std+2×): " + ("✅ PASS" if ok else "❌ FAIL")

    print(f"\n{'─' * 64}")
    print(f"  {variant}  |  {symbol}  |  n={std['n']} trades")
    print(f"{'─' * 64}")
    print(f"  {'Metric':<18} {'Standard':>12} {'2× Stress':>12}")
    print(f"  {'PF':<18} {std['pf']:>12.3f} {s2x['pf']:>12.3f}")
    print(f"  {'Win rate':<18} {std['wr']:>11.1f}% {s2x['wr']:>11.1f}%")
    print(f"  {'Avg R':<18} {std['avg_r']:>12.3f} {s2x['avg_r']:>12.3f}")
    print(f"  {'Max DD (R)':<18} {std['max_dd']:>12.2f} {s2x['max_dd']:>12.2f}")
    exits: dict[str, int] = {}
    for t in trades:
        exits[t.exit_reason] = exits.get(t.exit_reason, 0) + 1
    print(f"  Exit mix: {exits}")
    if gate:
        print(gate)
    monthly_breakdown(trades, "net_r_std")


def compare(baseline: list[Trade], combined: list[Trade]) -> None:
    print(f"\n{'═' * 64}")
    print("  COMPARISON — BASELINE (ST-A2) vs D2_COMBINED")
    print(f"{'═' * 64}")
    b = metrics(baseline, "net_r_std")
    b2 = metrics(baseline, "net_r_2x")
    c = metrics(combined, "net_r_std")
    c2 = metrics(combined, "net_r_2x")
    print(f"  {'':22} {'BASELINE':>10} {'D2_COMBINED':>12}")
    print(f"  {'Trades':22} {b['n']:>10} {c['n']:>12}")
    print(f"  {'PF (std)':22} {b['pf']:>10.3f} {c['pf']:>12.3f}")
    print(f"  {'PF (2× stress)':22} {b2['pf']:>10.3f} {c2['pf']:>12.3f}")
    print(f"  {'Win rate':22} {b['wr']:>9.1f}% {c['wr']:>11.1f}%")
    print(f"  {'Avg R':22} {b['avg_r']:>10.3f} {c['avg_r']:>12.3f}")
    print(f"  {'Max DD (R)':22} {b['max_dd']:>10.2f} {c['max_dd']:>12.2f}")
    if b["n"] > 0:
        filtered = b["n"] - c["n"]
        pct = round(filtered / b["n"] * 100, 1)
        print(f"\n  D2 gates removed {filtered}/{b['n']} signals ({pct}%)")
    print(f"{'═' * 64}\n")


def save_csv(trades: list[Trade], path: Path) -> None:
    fields = [
        "variant",
        "symbol",
        "session",
        "direction",
        "entry_time",
        "entry",
        "sl",
        "tp1",
        "sl_pips",
        "exit_time",
        "exit_price",
        "exit_reason",
        "gross_r",
        "net_r_std",
        "net_r_2x",
    ]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for t in trades:
            w.writerow(
                {
                    k: (
                        round(getattr(t, k), 4)
                        if isinstance(getattr(t, k), float)
                        else getattr(t, k)
                    )
                    for k in fields
                }
            )
    print(f"  Trade log → {path}")


# ── Entry point ───────────────────────────────────────────────────────────────


def main() -> None:
    p = argparse.ArgumentParser(
        description="6-month replay: ST-A2 baseline vs D2-combined"
    )
    p.add_argument("--symbols", nargs="+", default=["EURUSD", "GBPUSD"])
    p.add_argument("--start", default=None)
    p.add_argument("--end", default=None)
    p.add_argument(
        "--parquet",
        action="store_true",
        help="Load from data/processed/ Parquet files instead of CSV",
    )
    args = p.parse_args()

    # Set defaults based on mode
    if args.parquet:
        start = args.start or "2024-11-01"
        end = args.end or "2024-11-30"
    else:
        start = args.start or "2026-01-01T00:00:00Z"
        end = args.end or "2026-06-19T23:59:59Z"

    print(f"\n{'═' * 64}")
    print(f"  Mode: {'PARQUET (Dukascopy real ticks)' if args.parquet else 'CSV'}")
    print(f"  Period: {start} → {end}")
    print(f"  Symbols: {', '.join(args.symbols)}")
    print(f"{'═' * 64}")

    all_base: list[Trade] = []
    all_comb: list[Trade] = []

    for sym in args.symbols:
        if args.parquet:
            print(f"\n[{sym}] Loading Parquet …")
            c_m15 = load_parquet(sym, "M15", start, end)
            c_h4 = load_parquet(sym, "H4")  # full H4 for bias warm-up
            if not c_m15:
                print(f"[{sym}] No M15 data for range {start}→{end}, skipping")
                continue
        else:
            instr = sym[:3] + "_" + sym[3:]
            m15_path = DATA_DIR / f"{instr}_M15.csv"
            h4_path = DATA_DIR / f"{instr}_H4.csv"
            if not m15_path.exists() or not h4_path.exists():
                print(
                    f"[{sym}] Missing CSV. Run: python3 scripts/fetch_data.py --symbols {sym}"
                )
                continue
            print(f"\n[{sym}] Loading CSV …")
            c_m15 = filter_range(load_csv(m15_path), start, end)
            c_h4 = load_csv(h4_path)

        print(f"[{sym}] M15={len(c_m15)} bars | H4_full={len(c_h4)} bars")

        print(f"[{sym}] Running BASELINE (ST-A2) …")
        base = run_variant("BASELINE", sym, c_m15, c_h4, ST_A2_CONFIG)
        print_report("BASELINE", sym, base)
        all_base.extend(base)

        print(f"\n[{sym}] Running D2_COMBINED …")
        comb = run_variant("D2_COMBINED", sym, c_m15, c_h4, D2_CONFIG)
        print_report("D2_COMBINED", sym, comb)
        all_comb.extend(comb)

    compare(all_base, all_comb)

    out_dir = RPT_DIR if args.parquet else OUT_DIR
    out = out_dir / "replay_6m_trades.csv"
    save_csv(all_base + all_comb, out)


if __name__ == "__main__":
    main()
