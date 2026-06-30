"""
TRIAL_ST_A2_D1_001 — ST-A2 Baseline vs D1 Context A/B Replay.

Compares four variants over the same data, period, spread, and risk model:

  BASELINE      — pure ST-A2 (no D1 gates)
  D1_BIAS       — Gate A only  (D1 structure must agree with 4H bias)
  D1_LOCATION   — Gate B only  (session open in discount/premium zone)
  D1_ALL        — Gate A + Gate B combined

Gate C (POI proximity) is not tested here.
See TRIAL_ST_A2_D1_POI_001 for that sequence.

Uses:
  strategy/session_liquidity/ — ST-A2 canonical execution chain
  session_smc/daily_context.py — D1 context and gate evaluator

Usage:
    python3 scripts/replay_st_a2_d1.py
    python3 scripts/replay_st_a2_d1.py --symbols EURUSD --start 2026-01-01
    python3 scripts/replay_st_a2_d1.py --out-csv docs/d1_trial_trades.csv
"""

from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from session_smc.daily_context import apply_d1_gates, build_d1_context
from strategy.session_liquidity.bias_filter import htf_bias
from strategy.session_liquidity.displacement_detector import (
    detect_displacement, wilder_atr)
from strategy.session_liquidity.entry_engine import build_signal
from strategy.session_liquidity.session_builder import (build_asian_range,
                                                        classify_session)
from strategy.session_liquidity.sweep_detector import detect_sweep

# ── Constants ─────────────────────────────────────────────────────────────────

PIP = 0.0001
_UTC = timezone.utc

DATA_DIR = Path(__file__).parent.parent / "data" / "historical"
OUT_DIR = Path(__file__).parent.parent / "docs"

COSTS = {
    "EURUSD": {"standard": 1.4, "stress2x": 2.8},
    "GBPUSD": {"standard": 1.8, "stress2x": 3.6},
}

# ── ST-A2 execution parameters (matches ST-A2 Phase-0 defaults) ───────────────

ST_A2_EXEC = {
    "rr": 3.0,
    "sl_buffer_pips": 2.0,
    "displacement_mult": 1.2,
    "atr_period": 14,
    "sweep_timeout_bars": 4,
    "min_sl_pips": 5.0,
    "min_range_pips": {"EURUSD": 15.0, "GBPUSD": 20.0},
}

# ── D1 gate configs per variant ───────────────────────────────────────────────

VARIANTS: dict[str, dict] = {
    "BASELINE": {
        **ST_A2_EXEC,
        "d1_context_enabled": False,
        "d1_bias_filter": False,
        "d1_location_filter": False,
        "d1_poi_filter": False,  # always off (future trial)
    },
    "D1_BIAS": {
        **ST_A2_EXEC,
        "d1_context_enabled": True,
        "d1_bias_filter": True,
        "d1_location_filter": False,
        "d1_poi_filter": False,
    },
    "D1_LOCATION": {
        **ST_A2_EXEC,
        "d1_context_enabled": True,
        "d1_bias_filter": False,
        "d1_location_filter": True,
        "d1_poi_filter": False,
    },
    "D1_ALL": {
        **ST_A2_EXEC,
        "d1_context_enabled": True,
        "d1_bias_filter": True,
        "d1_location_filter": True,
        "d1_poi_filter": False,
    },
}


# ── Data loading ──────────────────────────────────────────────────────────────


def load_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append(
                {
                    "time": row["time"],
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                }
            )
    return rows


def filter_range(candles: list[dict], start: str, end: str) -> list[dict]:
    return [c for c in candles if start <= c["time"][:10] <= end[:10]]


def _utc(t) -> datetime:
    if isinstance(t, datetime):
        return t if t.tzinfo else t.replace(tzinfo=_UTC)
    return datetime.fromisoformat(str(t).replace("Z", "+00:00"))


# ── Trade container ───────────────────────────────────────────────────────────


@dataclass
class Trade:
    variant: str
    symbol: str
    session: str
    direction: str
    entry_time: str
    entry: float
    sl: float
    tp1: float
    sl_pips: float
    exit_time: str = ""
    exit_price: float = 0.0
    exit_reason: str = ""
    gross_r: float = 0.0
    net_r_std: float = 0.0
    net_r_2x: float = 0.0
    d1_bias: str = ""
    d1_location: str = ""


# ── Trade simulation ──────────────────────────────────────────────────────────


def simulate_trade(
    sig,
    day_bars: list[tuple[dict, str]],
    entry_bar_idx: int,
    symbol: str,
    session: str,
    variant: str,
    d1_ctx,
) -> "Trade | None":
    if sig is None:
        return None

    entry_price = sig.entry
    cost_std = COSTS.get(symbol, {}).get("standard", 1.4)
    cost_2x = COSTS.get(symbol, {}).get("stress2x", 2.8)
    entry_time = day_bars[entry_bar_idx][0]["time"]

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
        d1_bias=getattr(d1_ctx, "daily_bias", ""),
        d1_location=getattr(d1_ctx, "daily_location", ""),
    )

    is_long = sig.side == "long"

    for j in range(entry_bar_idx + 1, len(day_bars)):
        bar, _ = day_bars[j]
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
    variant_name: str,
    symbol: str,
    candles_m15: list[dict],
    candles_4h: list[dict],
    cfg: dict,
) -> list[Trade]:
    """Walk-forward replay for one variant over filtered M15 data."""
    sorted_m15 = sorted(candles_m15, key=lambda c: c["time"])
    sorted_4h = sorted(candles_4h, key=lambda c: c["time"])

    atrs = wilder_atr(sorted_m15, cfg["atr_period"])
    atr_map = {c["time"]: a for c, a in zip(sorted_m15, atrs)}

    min_range = cfg["min_range_pips"].get(symbol, 15.0)
    d1_on = cfg.get("d1_context_enabled", False)
    swing_n = cfg.get("swing_n", 3)

    # Pre-group killzone bars by UTC date
    kz_by_date: dict[date, list] = {}
    for c in sorted_m15:
        dt = _utc(c["time"])
        s = classify_session(dt)
        if s is not None:
            kz_by_date.setdefault(dt.date(), []).append((c, s))

    trades: list[Trade] = []

    for trade_date in sorted(kz_by_date.keys()):

        # ── Asian range ───────────────────────────────────────────────────────
        asian = build_asian_range(sorted_m15, trade_date)
        if asian is None or asian.range_pips < min_range:
            continue

        # ── London open for HTF bias reference ───────────────────────────────
        day_start_utc = datetime(
            trade_date.year, trade_date.month, trade_date.day, 7, 0, tzinfo=_UTC
        )
        bias = htf_bias(sorted_4h, day_start_utc)
        if bias == "neutral":
            continue

        # ── D1 context — built once per day ──────────────────────────────────
        d1_ctx = None
        if d1_on:
            d1_ctx = build_d1_context(sorted_4h, day_start_utc, swing_n=swing_n)
            if d1_ctx is None:
                continue  # insufficient daily history

        # ── Session walk ──────────────────────────────────────────────────────
        day_bars = kz_by_date[trade_date]
        session_traded: set = set()
        pending: dict | None = None

        for bar_idx, (candle, session) in enumerate(day_bars):
            if session in session_traded:
                continue

            if pending and pending["session"] != session:
                pending = None

            if pending is None:
                # ── D1 Gate B: location check at each sweep-candidate bar ─────
                if d1_on and d1_ctx is not None:
                    ok, _ = apply_d1_gates(
                        d1_ctx,
                        bias,
                        session_open_price=float(candle["open"]),
                        cfg={
                            "d1_bias_filter": cfg.get("d1_bias_filter", False),
                            "d1_location_filter": cfg.get("d1_location_filter", False),
                            "d1_poi_filter": False,
                        },
                    )
                    if not ok:
                        continue

                sweep = detect_sweep(candle, asian.high, asian.low, bias)
                if sweep.detected:
                    pending = {
                        "sweep": sweep,
                        "bar_idx": bar_idx,
                        "session": session,
                    }

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

                    # D1 Gate A (structure gate) is best evaluated at the sweep
                    # bar level where bias is known. Apply here as final check
                    # if not already applied at bar-level above.
                    if (
                        d1_on
                        and d1_ctx is not None
                        and cfg.get("d1_bias_filter", False)
                    ):
                        ok, _ = apply_d1_gates(
                            d1_ctx,
                            bias,
                            session_open_price=float(candle["open"]),
                            cfg={
                                "d1_bias_filter": True,
                                "d1_location_filter": False,
                                "d1_poi_filter": False,
                            },
                        )
                        if not ok:
                            continue

                    trade = simulate_trade(
                        sig, day_bars, bar_idx, symbol, session, variant_name, d1_ctx
                    )
                    if trade is not None:
                        trades.append(trade)
                        session_traded.add(session)

    return trades


# ── Metrics ───────────────────────────────────────────────────────────────────


def metrics(trades: list[Trade], r_field: str) -> dict:
    if not trades:
        return {
            "n": 0,
            "pf": 0.0,
            "wr": 0.0,
            "avg_r": 0.0,
            "max_dd": 0.0,
            "total_r": 0.0,
        }
    vals = [getattr(t, r_field) for t in trades]
    wins = sum(1 for v in vals if v > 0)
    g_win = sum(v for v in vals if v > 0)
    g_loss = abs(sum(v for v in vals if v <= 0))
    pf = g_win / g_loss if g_loss > 0 else float("inf")
    eq = peak = max_dd = 0.0
    for v in vals:
        eq += v
        if eq > peak:
            peak = eq
        dd = peak - eq
        if dd > max_dd:
            max_dd = dd
    return {
        "n": len(trades),
        "pf": round(pf, 3),
        "wr": round(wins / len(trades) * 100, 1),
        "avg_r": round(sum(vals) / len(trades), 3),
        "max_dd": round(max_dd, 2),
        "total_r": round(sum(vals), 3),
    }


def monthly_breakdown(trades: list[Trade], r_field: str) -> None:
    by_month: dict[str, list] = {}
    for t in trades:
        m = t.entry_time[:7]
        by_month.setdefault(m, []).append(getattr(t, r_field))
    if not by_month:
        return
    print(f"  {'Month':<10} {'n':>4} {'PF':>7} {'WR%':>6} {'AvgR':>7} {'MaxDD':>7}")
    print(f"  {'─'*47}")
    for month in sorted(by_month):
        vals = by_month[month]
        wins = sum(1 for v in vals if v > 0)
        g_w = sum(v for v in vals if v > 0)
        g_l = abs(sum(v for v in vals if v <= 0))
        pf = g_w / g_l if g_l > 0 else float("inf")
        wr = wins / len(vals) * 100
        avg = sum(vals) / len(vals)
        eq = peak = mx = 0.0
        for v in vals:
            eq += v
            if eq > peak:
                peak = eq
            d = peak - eq
            if d > mx:
                mx = d
        pf_s = f"{pf:.3f}" if pf != float("inf") else "∞"
        print(
            f"  {month:<10} {len(vals):>4} {pf_s:>7} {wr:>5.1f}% {avg:>7.3f} {mx:>7.2f}"
        )


def print_report(variant: str, symbol: str, trades: list[Trade]) -> None:
    std = metrics(trades, "net_r_std")
    s2x = metrics(trades, "net_r_2x")
    print(f"\n{'─'*60}")
    print(f"  {variant}  |  {symbol}  |  n={std['n']}")
    print(f"{'─'*60}")
    print(f"  {'Metric':<18} {'Standard':>12} {'2× Stress':>12}")
    print(f"  {'PF':<18} {std['pf']:>12.3f} {s2x['pf']:>12.3f}")
    print(f"  {'Win rate':<18} {std['wr']:>11.1f}% {s2x['wr']:>11.1f}%")
    print(f"  {'Avg R':<18} {std['avg_r']:>12.3f} {s2x['avg_r']:>12.3f}")
    print(f"  {'Max DD (R)':<18} {std['max_dd']:>12.2f} {s2x['max_dd']:>12.2f}")
    exits: dict[str, int] = {}
    for t in trades:
        exits[t.exit_reason] = exits.get(t.exit_reason, 0) + 1
    print(f"  Exit mix: {exits}")
    monthly_breakdown(trades, "net_r_std")


# ── Comparison table ──────────────────────────────────────────────────────────


def comparison_table(results: dict[str, list[Trade]]) -> None:
    """Print a side-by-side comparison of all variants."""
    baseline = results.get("BASELINE", [])
    base_std = metrics(baseline, "net_r_std")
    base_2x = metrics(baseline, "net_r_2x")

    print(f"\n{'═'*72}")
    print("  COMPARISON — All Variants vs BASELINE")
    print(f"{'═'*72}")
    hdr = f"  {'Variant':<15} {'n':>4} {'PF (std)':>10} {'PF (2x)':>10} {'WR%':>6} {'AvgR':>7} {'MaxDD':>7} {'Filtered%':>10}"
    print(hdr)
    print(f"  {'─'*67}")

    base_n = base_std["n"]
    for vname, trades in results.items():
        std = metrics(trades, "net_r_std")
        s2x = metrics(trades, "net_r_2x")
        n = std["n"]
        filtered_pct = round((base_n - n) / base_n * 100, 1) if base_n > 0 else 0.0
        pf_s = f"{std['pf']:.3f}" if std["pf"] != float("inf") else "∞"
        pf2_s = f"{s2x['pf']:.3f}" if s2x["pf"] != float("inf") else "∞"
        arrow = ""
        if vname != "BASELINE" and base_2x["pf"] > 0 and s2x["pf"] > 0:
            arrow = " ↑" if s2x["pf"] > base_2x["pf"] else " ↓"
        print(
            f"  {vname:<15} {n:>4} {pf_s:>10} {pf2_s+arrow:>10} "
            f"{std['wr']:>5.1f}% {std['avg_r']:>7.3f} {std['max_dd']:>7.2f} "
            f"{filtered_pct:>9.1f}%"
        )

    print(f"{'═'*72}\n")
    if base_n > 0:
        d1_all = results.get("D1_ALL", [])
        d1_std = metrics(d1_all, "net_r_std")
        d1_2x = metrics(d1_all, "net_r_2x")
        filtered = base_n - d1_std["n"]
        pct = round(filtered / base_n * 100, 1)
        print(f"  D1_ALL vs BASELINE: removed {filtered}/{base_n} signals ({pct}%)")
        if d1_2x["pf"] > base_2x["pf"]:
            print(f"  PF_2x: {base_2x['pf']:.3f} → {d1_2x['pf']:.3f}  ↑ IMPROVED")
        elif d1_2x["pf"] < base_2x["pf"]:
            print(f"  PF_2x: {base_2x['pf']:.3f} → {d1_2x['pf']:.3f}  ↓ DEGRADED")
        else:
            print(f"  PF_2x: {base_2x['pf']:.3f}  UNCHANGED")
        print()


# ── CSV export ────────────────────────────────────────────────────────────────


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
        "d1_bias",
        "d1_location",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
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
    print(f"  Trade log → {path.relative_to(path.parent.parent)}")


# ── Entry point ───────────────────────────────────────────────────────────────


def main() -> None:
    p = argparse.ArgumentParser(
        description="TRIAL_ST_A2_D1_001 — ST-A2 vs D1 context A/B replay"
    )
    p.add_argument("--symbols", nargs="+", default=["EURUSD", "GBPUSD"])
    p.add_argument("--start", default="2026-05-01")
    p.add_argument("--end", default="2026-06-30")
    p.add_argument("--out-csv", default=str(OUT_DIR / "st_a2_d1_trades.csv"))
    p.add_argument("--variants", nargs="+", default=list(VARIANTS.keys()))
    args = p.parse_args()

    print(f"\n{'═'*60}")
    print("  TRIAL_ST_A2_D1_001")
    print("  ST-A2 Baseline vs D1 Context Layer")
    print(f"  Period: {args.start} → {args.end}")
    print(f"  Symbols: {args.symbols}")
    print(f"  Variants: {args.variants}")
    print(f"{'═'*60}")

    all_results: dict[str, list[Trade]] = {v: [] for v in args.variants}

    for sym in args.symbols:
        instr = sym[:3] + "_" + sym[3:]
        m15_path = DATA_DIR / f"{instr}_M15.csv"
        h4_path = DATA_DIR / f"{instr}_H4.csv"

        if not m15_path.exists() or not h4_path.exists():
            print(
                f"\n[{sym}] Missing data files. Run: python3 scripts/fetch_data.py --symbols {sym}"
            )
            continue

        print(f"\n[{sym}] Loading data ...")
        c_m15_all = load_csv(m15_path)
        c_m15 = filter_range(c_m15_all, args.start, args.end)
        c_h4 = load_csv(h4_path)

        if not c_m15:
            print(f"[{sym}] No M15 data in period {args.start}–{args.end}. Skipping.")
            continue

        actual_end = max(c["time"][:10] for c in c_m15)
        print(
            f"[{sym}] M15 in period: {len(c_m15)} bars  "
            f"({c_m15[0]['time'][:10]} → {actual_end})"
        )
        print(f"[{sym}] H4 (full, for warm-up): {len(c_h4)} bars")

        print()
        for vname in args.variants:
            cfg = VARIANTS[vname]
            print(f"  [{sym}] Running {vname} ...", end=" ", flush=True)
            trades = run_variant(vname, sym, c_m15, c_h4, cfg)
            all_results[vname].extend(trades)
            std = metrics(trades, "net_r_std")
            s2x = metrics(trades, "net_r_2x")
            pf_s = f"{std['pf']:.3f}" if std["pf"] != float("inf") else "∞"
            pf2_s = f"{s2x['pf']:.3f}" if s2x["pf"] != float("inf") else "∞"
            print(f"n={std['n']}  PF_std={pf_s}  PF_2x={pf2_s}  WR={std['wr']}%")

    # ── Per-variant detailed report ────────────────────────────────────────────
    print(f"\n\n{'═'*60}")
    print("  DETAILED RESULTS BY VARIANT")
    print(f"{'═'*60}")
    for vname in args.variants:
        print_report(vname, "+".join(args.symbols), all_results[vname])

    # ── Comparison table ───────────────────────────────────────────────────────
    comparison_table(all_results)

    # ── CSV export ─────────────────────────────────────────────────────────────
    all_trades = [t for trades in all_results.values() for t in trades]
    if all_trades:
        save_csv(all_trades, Path(args.out_csv))

    # ── Gate summary ───────────────────────────────────────────────────────────
    baseline_2x = metrics(all_results.get("BASELINE", []), "net_r_2x")
    d1_all_2x = metrics(all_results.get("D1_ALL", []), "net_r_2x")

    print("  GATE SUMMARY (D1_ALL vs BASELINE at PF_2x > 1.0 threshold)")
    print(f"  BASELINE PF_2x = {baseline_2x['pf']:.3f}  (n={baseline_2x['n']})")
    print(f"  D1_ALL   PF_2x = {d1_all_2x['pf']:.3f}  (n={d1_all_2x['n']})")
    if d1_all_2x["n"] >= 10:
        verdict = "PASS" if d1_all_2x["pf"] > 1.0 else "FAIL"
        print(f"  D1 gate verdict (n≥10): {verdict}")
    else:
        print(f"  D1 gate verdict: INSUFFICIENT TRADES (n={d1_all_2x['n']} < 10)")
        print("  Cannot draw conclusions from this period alone.")
    print()


if __name__ == "__main__":
    main()
