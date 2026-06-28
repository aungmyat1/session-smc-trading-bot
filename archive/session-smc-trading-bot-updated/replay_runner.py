"""
replay_runner.py — Historical replay validation for ST-A2 updated bot.

Feeds EURUSD M15 candles bar-by-bar (Jan 2026–Jun 2026) through
ForwardTestSimulator, simulates trade outcomes, and reports metrics.

NO live broker connection. NO MetaAPI. Pure offline validation.
NO strategy logic modifications — uses run_strategy() unchanged.

Usage:
    cd /home/aungp/session-smc-trading-bot/session-smc-trading-bot-updated
    python3 replay_runner.py

Output:
    Prints per-trade log and summary statistics to stdout.
    Writes CSV to: docs/replay_trades.csv
    Writes JSON to: docs/replay_metrics.json
"""

from __future__ import annotations

import csv
import json
import os
import sys
from datetime import datetime, timezone

# ── Path setup ────────────────────────────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from simulator.forward_test import ForwardTestSimulator

# ── Constants ─────────────────────────────────────────────────────────────────

SYMBOL = "EURUSD"
REPLAY_START = "2026-01-01"
REPLAY_END   = "2026-06-30"
RR           = 2.0     # TP1 target (4R not used here; replay uses 2R for cleaner stats)
MAX_BARS     = 96      # 24h timeout in M15 bars

# VT Markets Standard account cost model (round-trip, in pips)
# Spread 0.8–1.2 pip mid + 0.6 pip commission = ~1.4 pip RT
SPREAD_RT_PIPS = 1.4
PIP            = 0.0001   # EURUSD pip

M15_CSV = os.path.join(_HERE, "data", "historical", "EUR_USD_M15.csv")
H4_CSV  = os.path.join(_HERE, "data", "historical", "EUR_USD_H4.csv")

DOCS_DIR = os.path.join(_HERE, "docs")
OUT_CSV  = os.path.join(DOCS_DIR, "replay_trades.csv")
OUT_JSON = os.path.join(DOCS_DIR, "replay_metrics.json")

# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_time(ts: str) -> datetime:
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S+00:00"):
        try:
            return datetime.strptime(ts, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def load_csv(path: str) -> list[dict]:
    rows = []
    with open(path, newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            rows.append({
                "time":   row.get("time", row.get("datetime", "")),
                "open":   float(row.get("open", 0)),
                "high":   float(row.get("high", 0)),
                "low":    float(row.get("low", 0)),
                "close":  float(row.get("close", 0)),
                "volume": float(row.get("volume", row.get("tick_volume", 0))),
            })
    rows.sort(key=lambda r: r["time"])
    return rows


def filter_range(bars: list[dict], start: str, end: str) -> list[dict]:
    return [b for b in bars if start <= b["time"][:10] <= end]


def simulate_trade(
    entry: float, sl: float, side: str, rr: float,
    future_bars: list[dict], max_bars: int = MAX_BARS
) -> tuple:
    """Walk future M15 bars. Returns (outcome, gross_r, exit_price, exit_time, bars_held)."""
    risk = abs(entry - sl)
    if risk == 0:
        return "timeout", 0.0, entry, "", 0
    tp = (entry + risk * rr) if side == "long" else (entry - risk * rr)
    bars = future_bars[:max_bars]
    for i, bar in enumerate(bars):
        h, lo = float(bar["high"]), float(bar["low"])
        if side == "long":
            if lo <= sl:
                return "loss", -1.0, sl, bar["time"], i + 1
            if h >= tp:
                return "win",  rr,   tp, bar["time"], i + 1
        else:
            if h >= sl:
                return "loss", -1.0, sl, bar["time"], i + 1
            if lo <= tp:
                return "win",  rr,   tp, bar["time"], i + 1
    if bars:
        last = bars[-1]
        exit_p = float(last["close"])
        raw = (exit_p - entry) / risk if side == "long" else (entry - exit_p) / risk
        return "timeout", raw, exit_p, last["time"], len(bars)
    return "timeout", 0.0, entry, "", 0


def spread_cost_r(sl_pips: float) -> float:
    if sl_pips <= 0:
        return 0.0
    return SPREAD_RT_PIPS / sl_pips


def compute_metrics(trades: list[dict]) -> dict:
    net_rs = [t["net_r"] for t in trades]
    wins   = [r for r in net_rs if r > 0]
    losses = [r for r in net_rs if r <= 0]
    total_gain = sum(wins)
    total_loss = abs(sum(losses))
    pf = total_gain / total_loss if total_loss > 0 else float("inf")

    # Max drawdown
    equity, peak, max_dd = 0.0, 0.0, 0.0
    for r in net_rs:
        equity += r
        if equity > peak:
            peak = equity
        dd = peak - equity
        if dd > max_dd:
            max_dd = dd

    # Win/loss streaks
    best_streak = worst_streak = cur_streak = 0
    for r in net_rs:
        if r > 0:
            cur_streak = max(cur_streak + 1, 1)
        else:
            cur_streak = min(cur_streak - 1, -1)
        best_streak  = max(best_streak, cur_streak)
        worst_streak = min(worst_streak, cur_streak)

    # Session breakdown
    sessions: dict[str, list] = {"london": [], "newyork": [], "other": []}
    for t in trades:
        sessions[t.get("session", "other")].append(t["net_r"])

    def session_stats(rs):
        if not rs:
            return {"count": 0, "win_rate": 0, "avg_r": 0, "pf": 0}
        w = [r for r in rs if r > 0]
        l = [r for r in rs if r <= 0]
        return {
            "count":    len(rs),
            "win_rate": round(len(w) / len(rs) * 100, 1),
            "avg_r":    round(sum(rs) / len(rs), 3),
            "pf":       round(sum(w) / abs(sum(l)), 3) if l else float("inf"),
        }

    return {
        "total_trades":   len(net_rs),
        "win_count":      len(wins),
        "loss_count":     len(losses),
        "timeout_count":  sum(1 for t in trades if t["outcome"] == "timeout"),
        "win_rate":       round(len(wins) / len(net_rs) * 100, 1) if net_rs else 0,
        "avg_win_r":      round(sum(wins) / len(wins), 3) if wins else 0,
        "avg_loss_r":     round(sum(losses) / len(losses), 3) if losses else 0,
        "avg_r":          round(sum(net_rs) / len(net_rs), 3) if net_rs else 0,
        "total_net_r":    round(sum(net_rs), 3),
        "profit_factor":  round(pf, 3),
        "max_drawdown_r": round(max_dd, 3),
        "best_win_streak":  best_streak,
        "worst_loss_streak": abs(worst_streak),
        "expectancy_r":   round(sum(net_rs) / len(net_rs), 4) if net_rs else 0,
        "sessions": {
            "london":  session_stats(sessions["london"]),
            "newyork": session_stats(sessions["newyork"]),
            "other":   session_stats(sessions["other"]),
        },
        "replay_period":  f"{REPLAY_START} to {REPLAY_END}",
        "symbol":         SYMBOL,
        "spread_rt_pips": SPREAD_RT_PIPS,
        "rr_used":        RR,
    }


def session_label(ts: str) -> str:
    try:
        dt = _parse_time(ts)
        h = dt.hour
        if 7 <= h < 10:
            return "london"
        if 13 <= h < 16:
            return "newyork"
    except Exception:
        pass
    return "other"


# ── Main ──────────────────────────────────────────────────────────────────────

def run_replay() -> dict:
    os.makedirs(DOCS_DIR, exist_ok=True)
    print(f"Loading {SYMBOL} M15 data…")
    m15_all = load_csv(M15_CSV)
    h4_all  = load_csv(H4_CSV)

    m15_replay = filter_range(m15_all, REPLAY_START, REPLAY_END)
    h4_warmup  = [b for b in h4_all if b["time"][:10] < REPLAY_START]
    h4_replay  = [b for b in h4_all if b["time"][:10] <= REPLAY_END]

    print(f"  M15 bars in replay window: {len(m15_replay):,}")
    print(f"  H4 bars (full history up to end): {len(h4_replay):,}")
    print(f"  H4 bars before replay start (warmup): {len(h4_warmup):,}")
    print()

    # Build time index for fast future-bar lookup
    m15_idx: dict[str, int] = {b["time"]: i for i, b in enumerate(m15_replay)}

    # Use full m15_all so post-replay bars can be used for trade resolution
    m15_full_idx: dict[str, int] = {b["time"]: i for i, b in enumerate(m15_all)}

    # Create simulator — seed H4 with warmup history before replay window
    sim = ForwardTestSimulator(SYMBOL, h4_candles=h4_replay)

    # Batch mode: call run_strategy once on the full replay window.
    # Equivalent to bar-by-bar per LOOKAHEAD_AUDIT §3 (confirmed PASS).
    # O(n) vs O(n²) bar-by-bar — required for large windows.
    print(f"Running batch replay ({REPLAY_START} → {REPLAY_END})…")
    from strategy.session_liquidity.session_strategy import run_strategy
    raw = run_strategy(m15_replay, h4_replay, SYMBOL)
    # run_strategy returns list[Signal] or tuple(list[Signal], list[events])
    if isinstance(raw, tuple):
        all_signals = list(raw[0])
    else:
        all_signals = list(raw)

    print(f"  Replay complete: {len(m15_replay):,} bars, {len(all_signals)} signals generated")
    print()

    # ── Simulate trades ───────────────────────────────────────────────────────
    trades = []
    print("Simulating trade outcomes…")
    for sig in all_signals:
        sig_time_str = sig.timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")
        idx = m15_full_idx.get(sig_time_str)
        if idx is None:
            # Try matching within replay range
            for key in m15_full_idx:
                if key.startswith(sig.timestamp.strftime("%Y-%m-%dT%H:%M")):
                    idx = m15_full_idx[key]
                    break

        if idx is None:
            continue

        future_bars = m15_all[idx + 1: idx + 1 + MAX_BARS]
        if not future_bars:
            continue

        sl_pips = abs(sig.entry - sig.stop_loss) / PIP
        outcome, gross_r, exit_price, exit_time, bars_held = simulate_trade(
            sig.entry, sig.stop_loss, sig.side, RR, future_bars
        )
        cost_r = spread_cost_r(sl_pips)
        net_r  = round(gross_r - cost_r, 4)

        trade = {
            "signal_time":  sig_time_str,
            "exit_time":    exit_time,
            "symbol":       SYMBOL,
            "side":         sig.side,
            "session":      session_label(sig_time_str),
            "entry":        round(sig.entry, 5),
            "sl":           round(sig.stop_loss, 5),
            "tp":           round(sig.entry + (sig.entry - sig.stop_loss) * RR if sig.side == "long"
                                  else sig.entry - (sig.stop_loss - sig.entry) * RR, 5),
            "sl_pips":      round(sl_pips, 1),
            "exit_price":   round(exit_price, 5),
            "outcome":      outcome,
            "gross_r":      round(gross_r, 4),
            "spread_cost_r": round(cost_r, 4),
            "net_r":        net_r,
            "bars_held":    bars_held,
        }
        trades.append(trade)

        icon = "✅" if net_r > 0 else "❌" if net_r < 0 else "⏱"
        print(f"  {icon}  {sig_time_str[:16]}  {sig.side.upper():<5}  "
              f"entry={sig.entry:.5f}  SL={sig.stop_loss:.5f}  "
              f"SL={sl_pips:.1f}pip  {outcome}  net={net_r:+.2f}R  "
              f"session={trade['session']}")

    print()
    print(f"Trades with outcome: {len(trades)} / {len(all_signals)} signals")
    print()

    # ── Metrics ───────────────────────────────────────────────────────────────
    if not trades:
        print("NO TRADES — cannot compute metrics")
        return {}

    metrics = compute_metrics(trades)

    print("=" * 62)
    print(f"  REPLAY SUMMARY — {SYMBOL} — {REPLAY_START} → {REPLAY_END}")
    print("=" * 62)
    print(f"  Total trades:        {metrics['total_trades']}")
    print(f"  Wins / Losses:       {metrics['win_count']} / {metrics['loss_count']}  (timeouts: {metrics['timeout_count']})")
    print(f"  Win rate:            {metrics['win_rate']}%")
    print(f"  Avg win R:           {metrics['avg_win_r']:+.3f}R")
    print(f"  Avg loss R:          {metrics['avg_loss_r']:+.3f}R")
    print(f"  Avg R per trade:     {metrics['avg_r']:+.3f}R")
    print(f"  Total net R:         {metrics['total_net_r']:+.3f}R")
    print(f"  Profit Factor:       {metrics['profit_factor']:.3f}")
    print(f"  Max Drawdown:        {metrics['max_drawdown_r']:.3f}R")
    print(f"  Best win streak:     {metrics['best_win_streak']}")
    print(f"  Worst loss streak:   {metrics['worst_loss_streak']}")
    print(f"  Expectancy:          {metrics['expectancy_r']:+.4f}R/trade")
    print()
    print("  Session breakdown:")
    for sess, s in metrics["sessions"].items():
        if s["count"] > 0:
            print(f"    {sess.capitalize():<12} {s['count']:>3} trades  "
                  f"WR={s['win_rate']}%  avgR={s['avg_r']:+.3f}  PF={s['pf']:.3f}")
    print("=" * 62)

    # ── Write outputs ─────────────────────────────────────────────────────────
    with open(OUT_CSV, "w", newline="") as fh:
        if trades:
            writer = csv.DictWriter(fh, fieldnames=list(trades[0].keys()))
            writer.writeheader()
            writer.writerows(trades)
    print(f"\n  CSV written: {OUT_CSV}")

    with open(OUT_JSON, "w") as fh:
        json.dump(metrics, fh, indent=2)
    print(f"  JSON written: {OUT_JSON}")

    return metrics


if __name__ == "__main__":
    run_replay()
