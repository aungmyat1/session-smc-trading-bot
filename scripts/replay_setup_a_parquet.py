"""
Full 11-phase Setup A replay on Dukascopy Parquet data.

Signal chain (session_smc/confirmation_entry.py):
  Phase 1  Session active
  Phase 2  HTF Bias (4H + 1H)
  Phase 3  Session range build (first 8 bars = 2h)
  Phase 4  Session classification
  Phase 5  Liquidity sweep of session H/L
  Phase 6  15M CHoCH
  Phase 7  15M BOS
  Phase 8  15M Displacement (≥ 1.5× ATR14)
  Phase 9  15M FVG + retest
  Phase 10 Risk params  SL = tighter(25% range | wick ± 3pip)  TP1=4R  TP2=5R
  Phase 11 Min bars remaining

Entry:  close of FVG retest bar (bar-close, no lookahead)
D2 gates: disabled by default (isolates core 11-phase chain).
          Use --d2-gates to enable all three D2 context filters.

Window note:
  CHoCH+BOS+FVG retest requires ≥ 8h after session open to complete reliably.
  The original backtest.py uses 5h (20 bars) — too narrow, produces 0 signals.
  Default here is --session-bars 48 (12h window). London and NY sessions are
  evaluated independently; each gets its own 12h forward window. The session
  range is still built from the first 8 bars (2h) per the original spec.

Data:   data/processed/{SYMBOL}/{M15,H1,H4}.parquet  (Dukascopy tick-derived)
Output: reports/SETUP_A_PARQUET_REPORT.md

Usage:
    python3 scripts/replay_setup_a_parquet.py
    python3 scripts/replay_setup_a_parquet.py --symbol EURUSD --start 2024-01-01 --end 2024-12-31
    python3 scripts/replay_setup_a_parquet.py --session-bars 32
    python3 scripts/replay_setup_a_parquet.py --d2-gates
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from session_smc.confirmation_entry import generate_signal_A, DEFAULT_CONFIG

REPORTS = ROOT / "reports"
REPORTS.mkdir(exist_ok=True)
DATA_PROC = ROOT / "data" / "processed"

COSTS = {
    "EURUSD": {"standard": 1.4, "stress2x": 2.8},
    "GBPUSD": {"standard": 1.8, "stress2x": 3.6},
}
PIP = 0.0001
SESSION_BARS_DEFAULT = 48   # 12h window — minimum needed for CHoCH+BOS+FVG to complete
SESSION_ADVANCE = 12        # advance by one 3h session (12 bars) so each session is evaluated independently


# ── Data loading ──────────────────────────────────────────────────────────────

def load_parquet(symbol: str, tf: str, start: str = None, end: str = None) -> list[dict]:
    path = DATA_PROC / symbol / f"{tf}.parquet"
    if not path.exists():
        print(f"  [MISSING] {path}")
        return []
    df = pd.read_parquet(path, columns=["timestamp_utc", "open", "high", "low", "close", "volume"])
    df["time"] = pd.to_datetime(df["timestamp_utc"], utc=True).dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    if start:
        df = df[df["time"] >= start]
    if end:
        df = df[df["time"] <= end + "T23:59:59Z"]
    return df[["time", "open", "high", "low", "close", "volume"]].to_dict("records")


# ── Trade representation ──────────────────────────────────────────────────────

@dataclass
class Trade:
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
    exit_reason: str = ""   # "TP1" | "SL" | "SESSION_END"
    gross_r: float = 0.0
    net_r_standard: float = 0.0
    net_r_stress: float = 0.0
    # diagnostic
    sweep_idx: int = 0
    choch_idx: int = 0
    bos_idx: int = 0
    disp_idx: int = 0
    retest_idx: int = 0


# ── Replay core (mirrors backtest.py logic exactly) ───────────────────────────

def _weekday(time_str: str) -> int:
    return datetime.fromisoformat(time_str.replace("Z", "+00:00")).weekday()


def _closed_slice(sorted_bars: list[dict], before_time: str, bar_hours: int, count: int) -> list[dict]:
    cutoff_dt = (
        datetime.fromisoformat(before_time.replace("Z", "+00:00"))
        - timedelta(hours=bar_hours)
    )
    cutoff = cutoff_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    result = [c for c in sorted_bars if c["time"] <= cutoff]
    return result[-count:] if result else []


def _simulate(sig, session_candles: list[dict], symbol: str, session: str) -> "Trade | None":
    ri = sig.retest_idx
    if ri >= len(session_candles):
        return None

    entry_bar = session_candles[ri]
    entry_price = float(entry_bar["close"])

    cost_std    = COSTS.get(symbol, {}).get("standard", 1.4)
    cost_stress = COSTS.get(symbol, {}).get("stress2x", 2.8)

    t = Trade(
        symbol=symbol, session=session,
        direction=sig.direction,
        entry=entry_price, sl=float(sig.sl), tp1=float(sig.tp1),
        sl_pips=float(sig.sl_pips),
        entry_time=entry_bar["time"],
        sweep_idx=sig.sweep_idx, choch_idx=sig.choch_idx,
        bos_idx=sig.bos_idx, disp_idx=sig.displacement_idx,
        retest_idx=ri,
    )

    is_long = sig.direction == "long"
    for j in range(ri + 1, len(session_candles)):
        bar = session_candles[j]
        is_last = j == len(session_candles) - 1
        if is_long:
            if bar["low"] <= sig.sl:
                t.exit_price, t.exit_reason, t.exit_time = sig.sl, "SL", bar["time"]
                break
            if bar["high"] >= sig.tp1:
                t.exit_price, t.exit_reason, t.exit_time = sig.tp1, "TP1", bar["time"]
                break
        else:
            if bar["high"] >= sig.sl:
                t.exit_price, t.exit_reason, t.exit_time = sig.sl, "SL", bar["time"]
                break
            if bar["low"] <= sig.tp1:
                t.exit_price, t.exit_reason, t.exit_time = sig.tp1, "TP1", bar["time"]
                break
        if is_last:
            t.exit_price, t.exit_reason, t.exit_time = float(bar["close"]), "SESSION_END", bar["time"]

    if not t.exit_time:
        last = session_candles[-1]
        t.exit_price, t.exit_reason, t.exit_time = float(last["close"]), "SESSION_END", last["time"]

    if t.sl_pips <= 0:
        return None

    gross_pips = (t.exit_price - entry_price) / PIP if is_long else (entry_price - t.exit_price) / PIP
    t.gross_r           = gross_pips / t.sl_pips
    t.net_r_standard    = t.gross_r - cost_std / t.sl_pips
    t.net_r_stress      = t.gross_r - cost_stress / t.sl_pips
    return t


def run_symbol(
    symbol: str,
    m15: list[dict],
    h4: list[dict],
    h1: list[dict],
    cfg: dict,
    session_bars: int = SESSION_BARS_DEFAULT,
) -> list[Trade]:
    """Walk forward across all sessions.

    Each session (London 07:00 or NY 13:00) is evaluated independently.
    The signal window extends `session_bars` bars forward from session open,
    but the loop advances only SESSION_ADVANCE (12 bars = 3h) so both
    London and NY always get their own evaluation pass.
    """
    trades: list[Trade] = []
    n = len(m15)
    h4s = sorted(h4, key=lambda c: c["time"])
    h1s = sorted(h1, key=lambda c: c["time"])

    # Track which (date, session) pairs already produced a trade (one trade per session per day)
    traded: set = set()

    i = 0
    while i < n:
        bar = m15[i]
        t = bar["time"]
        hour   = int(t[11:13])
        minute = int(t[14:16])

        if _weekday(t) >= 5:
            i += 1
            continue

        if hour == 7 and minute == 0:
            sess = "london"
        elif hour == 13 and minute == 0:
            sess = "ny"
        else:
            i += 1
            continue

        sess_key = (t[:10], sess)
        if sess_key in traded:
            i += SESSION_ADVANCE
            continue

        sess_end = min(i + session_bars, n)
        sc = m15[i:sess_end]
        if len(sc) < cfg.get("session_range_bars", 8) + 2:
            i += SESSION_ADVANCE
            continue

        ctx_4h = _closed_slice(h4s, t, bar_hours=4, count=200)
        ctx_1h = _closed_slice(h1s, t, bar_hours=1, count=200) if h1s else m15[max(0, i - 200):i]

        if not ctx_4h or not ctx_1h:
            i += SESSION_ADVANCE
            continue

        sig = generate_signal_A(
            symbol=symbol,
            candles_4h=ctx_4h,
            candles_1h=ctx_1h,
            session_candles=sc,
            session_name=sess,
            config=cfg,
        )

        if sig is not None:
            trade = _simulate(sig, sc, symbol, sess)
            if trade is not None:
                trades.append(trade)
                traded.add(sess_key)

        i += SESSION_ADVANCE

    return trades


# ── Metrics ───────────────────────────────────────────────────────────────────

def _metrics(trades: list[Trade], field: str) -> dict:
    if not trades:
        return {"n": 0, "pf": 0.0, "win_rate": 0.0, "avg_r": 0.0, "max_dd": 0.0, "total_r": 0.0}
    vals   = [getattr(t, field) for t in trades]
    wins   = [v for v in vals if v > 0]
    losses = [v for v in vals if v <= 0]
    gw = sum(wins)
    gl = abs(sum(losses))
    pf = gw / gl if gl > 0 else (float("inf") if gw > 0 else 0.0)
    eq = peak = mdd = 0.0
    for v in vals:
        eq += v
        peak = max(peak, eq)
        mdd = max(mdd, peak - eq)
    return {
        "n": len(trades), "pf": round(pf, 3),
        "win_rate": round(len(wins) / len(trades) * 100, 1),
        "avg_r": round(sum(vals) / len(trades), 4),
        "max_dd": round(mdd, 2),
        "total_r": round(sum(vals), 3),
    }


# ── Report writers ────────────────────────────────────────────────────────────

def _pf(v: float) -> str:
    return "∞" if v == float("inf") else f"{v:.3f}"


def print_and_write_report(symbol: str, trades: list[Trade], start: str, end: str, d2_on: bool, session_bars: int = 48) -> None:
    std    = _metrics(trades, "net_r_standard")
    stress = _metrics(trades, "net_r_stress")
    gross  = _metrics(trades, "gross_r")

    gate = std["n"] >= 50 and std["pf"] > 1.0 and stress["pf"] > 1.0
    status = "✅ PASS" if gate else "❌ FAIL"

    by_month: dict[str, list] = {}
    by_sess:  dict[str, list] = {}
    by_exit:  dict[str, int]  = {}
    for t in trades:
        mo = t.entry_time[:7]
        by_month.setdefault(mo, []).append(t)
        by_sess.setdefault(t.session, []).append(t)
        by_exit[t.exit_reason] = by_exit.get(t.exit_reason, 0) + 1

    d2_label = "ON (d2_structure + d2_location + d2_poi)" if d2_on else "OFF (pure 11-phase baseline)"
    win_h = session_bars * 15 // 60
    win_m = session_bars * 15 % 60

    lines = [
        "# Setup A — Full 11-Phase Replay Report (Dukascopy Parquet)",
        f"Symbol: {symbol} | Period: {start} → {end}",
        f"Session window: {session_bars} bars ({win_h}h{win_m:02d}m) | Session range: first 8 bars (2h) | Advance: 12 bars (3h)",
        f"D2 context gates: {d2_label}",
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        "",
        "## Core Metrics",
        "",
        "| Metric | Gross | Net (std 1.4pip) | Net (2× stress 2.8pip) |",
        "|---|---|---|---|",
        f"| Trades (n) | {gross['n']} | {std['n']} | {stress['n']} |",
        f"| Win Rate | {gross['win_rate']}% | {std['win_rate']}% | {stress['win_rate']}% |",
        f"| Profit Factor | {_pf(gross['pf'])} | {_pf(std['pf'])} | {_pf(stress['pf'])} |",
        f"| Avg R | {gross['avg_r']:+.4f} | {std['avg_r']:+.4f} | {stress['avg_r']:+.4f} |",
        f"| Total R | {gross['total_r']:+.3f} | {std['total_r']:+.3f} | {stress['total_r']:+.3f} |",
        f"| Max DD | {gross['max_dd']:.2f}R | {std['max_dd']:.2f}R | {stress['max_dd']:.2f}R |",
        "",
        f"**Phase-0 gate (n≥50 AND PF>1.0 std AND 2×): {status}**",
        "",
        "## Monthly Breakdown (net std)",
        "",
        "| Month | n | WR% | PF | Total R |",
        "|---|---|---|---|---|",
    ]
    for mo in sorted(by_month):
        m = _metrics(by_month[mo], "net_r_standard")
        lines.append(f"| {mo} | {m['n']} | {m['win_rate']}% | {_pf(m['pf'])} | {m['total_r']:+.3f}R |")

    lines += [
        "",
        "## Session Breakdown (net std)",
        "",
        "| Session | n | WR% | PF | Total R | Max DD |",
        "|---|---|---|---|---|---|",
    ]
    for sess in sorted(by_sess):
        m = _metrics(by_sess[sess], "net_r_standard")
        lines.append(f"| {sess} | {m['n']} | {m['win_rate']}% | {_pf(m['pf'])} | {m['total_r']:+.3f}R | {m['max_dd']:.2f}R |")

    lines += [
        "",
        f"## Exit Breakdown",
        "",
        f"| Exit | Count |",
        "|---|---|",
    ]
    for ex, cnt in sorted(by_exit.items()):
        lines.append(f"| {ex} | {cnt} |")

    lines += ["", "## Trade Ledger", "", "| # | Date | Time UTC | Session | Dir | SL pip | Gross R | Net R | Exit |", "|---|---|---|---|---|---|---|---|---|"]
    for i, t in enumerate(trades, 1):
        lines.append(
            f"| {i} | {t.entry_time[:10]} | {t.entry_time[11:16]} | {t.session} | {t.direction} "
            f"| {t.sl_pips:.1f} | {t.gross_r:+.3f} | {t.net_r_standard:+.3f} | {t.exit_reason} |"
        )

    out = REPORTS / "SETUP_A_PARQUET_REPORT.md"
    out.write_text("\n".join(lines))
    print(f"\n  Report written: {out}")

    # Console summary
    print(f"\n{'─'*60}")
    print(f"  {symbol} | Setup A 11-phase | {start} → {end}")
    print(f"  Window: {session_bars} bars ({win_h}h{win_m:02d}m) | D2 gates: {d2_label}")
    print(f"{'─'*60}")
    print(f"  n={std['n']}  WR={std['win_rate']}%  PF_std={_pf(std['pf'])}  PF_2x={_pf(stress['pf'])}")
    print(f"  AvgR={std['avg_r']:+.4f}  TotalR={std['total_r']:+.3f}  MaxDD={std['max_dd']:.2f}R")
    print(f"  Exit breakdown: {by_exit}")
    print(f"  Gate (n≥50 AND PF>1.0 std AND 2×): {status}")
    print(f"{'─'*60}")


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="11-phase Setup A replay on Dukascopy Parquet")
    parser.add_argument("--symbol",    default="EURUSD")
    parser.add_argument("--start",     default="2024-01-01")
    parser.add_argument("--end",       default="2024-12-31")
    parser.add_argument("--session-bars", type=int, default=SESSION_BARS_DEFAULT,
                        help=f"Bars per session window (default {SESSION_BARS_DEFAULT} = 12h). "
                             "CHoCH+BOS+FVG needs ≥ 32 bars (8h) to complete. "
                             "Original backtest.py used 20 (5h) which produces 0 signals.")
    parser.add_argument("--d2-gates",  action="store_true",
                        help="Enable D2 context gates (structure + location + POI). Default: off.")
    args = parser.parse_args()

    sym = args.symbol
    print(f"\n[Setup A Parquet Replay]  {sym}  {args.start} → {args.end}")
    print(f"  Session window: {args.session_bars} bars ({args.session_bars*15//60}h{args.session_bars*15%60:02d}m)")
    print(f"  D2 gates: {'ON' if args.d2_gates else 'OFF'}")

    # Load data — H4 and H1 context start from a year before so bias has warmup
    ctx_start = f"{int(args.start[:4]) - 1}-{args.start[5:]}"

    print(f"  Loading M15 (ctx from {ctx_start}) …")
    m15 = load_parquet(sym, "M15", ctx_start, args.end)
    print(f"  Loading H4 …")
    h4  = load_parquet(sym, "H4", None, args.end)
    print(f"  Loading H1 …")
    h1  = load_parquet(sym, "H1", None, args.end)

    if not m15 or not h4:
        print("  ERROR: M15 or H4 data missing — run build_timeframes.py first")
        sys.exit(1)

    print(f"  M15={len(m15)} bars | H4={len(h4)} bars | H1={len(h1)} bars")
    print(f"  Running signal chain …")

    cfg = {
        **DEFAULT_CONFIG,
        "atr_period":  14,
        "swing_n":     3,
        "d2_structure_gate": args.d2_gates,
        "d2_location_gate":  args.d2_gates,
        "d2_poi_gate":       args.d2_gates,
    }

    # Filter M15 to requested date range only (H4/H1 load full history for bias context)
    m15_range = [b for b in m15 if args.start <= b["time"][:10] <= args.end]
    print(f"  M15 in replay window: {len(m15_range)} bars")

    trades = run_symbol(sym, m15_range, h4, h1, cfg, session_bars=args.session_bars)
    print(f"  Trades generated: {len(trades)}")

    print_and_write_report(sym, trades, args.start, args.end, args.d2_gates, session_bars=args.session_bars)


if __name__ == "__main__":
    main()
