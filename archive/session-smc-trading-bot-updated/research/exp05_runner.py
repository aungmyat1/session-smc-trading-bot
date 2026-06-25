#!/usr/bin/env python3
"""
EXP05 — ST-A2 Pre-Demo Optimization Runner.

Pre-registration: research/EXP05_OPTIMIZATION_REPORT.md (project root).
Isolation contract: touches nothing in strategy/ or execution/.

Baseline: run_strategy() over full history (sweep + displacement; no CHoCH/BOS/FVG).
Variants: post-hoc filters over the baseline signal set.

  A — exclude GBPUSD London
  B — NY only (exclude all London)
  C — B + stricter HTF bias (swing_n=3 + 1H agreement where H1 data present)
  D — C + 15M CHoCH+BOS gate (session_smc reused, entry/SL/TP unchanged)
  E — fee-floor filter on best-PF₂ₓ of {Base,A,B,C,D}; sweeps ceiling 0.10–0.30

Usage:
    python3 research/exp05_runner.py
    python3 research/exp05_runner.py --rr 5.0 --min-trades 100

Exit code 2 if a required CSV is missing.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from strategy.session_liquidity.session_strategy import run_strategy, DEFAULT_CONFIG
from strategy.session_liquidity.session_builder import classify_session
from session_smc.structure_detector import (
    htf_bias as htf_bias_combined,
    detect_choch,
    detect_bos,
)
from session_smc.swing_detector import last_swing_high, last_swing_low

_UTC = timezone.utc
_PIP = 0.0001

# ── Constants ─────────────────────────────────────────────────────────────────

SYMBOLS = ["EURUSD", "GBPUSD"]

DATA_DIR = ROOT / "data" / "historical"
OUT_DIR  = ROOT / "research"

_M15 = {"EURUSD": "EUR_USD_M15.csv", "GBPUSD": "GBP_USD_M15.csv"}
_H4  = {"EURUSD": "EUR_USD_H4.csv",  "GBPUSD": "GBP_USD_H4.csv"}
_H1  = {"EURUSD": "EUR_USD_H1.csv",  "GBPUSD": "GBP_USD_H1.csv"}

SPREAD = {
    "EURUSD": {"standard": 1.4, "2x": 2.8},
    "GBPUSD": {"standard": 1.8, "2x": 3.6},
}

MAX_SIM_BARS    = 96  # 24 h at M15 — matches existing backtest
SESSION_BARS    = 20  # session window size
PRE_SESSION_BARS = 30 # pre-session M15 bars prepended to ctx for CHoCH/BOS lookback
CHOCH_LOOKBACK  = 8   # matching session_smc.confirmation_entry DEFAULT_CONFIG
BOS_SWING_N     = 3   # matching session_smc.confirmation_entry DEFAULT_CONFIG

# EXP05 §1 targets — all four must hold on the best variant to PASS
TARGETS: dict = {
    "pf_2x":    1.25,
    "win_rate": 0.40,
    "max_dd":   15.0,
    "n_min":    100,
}

# Variant E fee-floor sweep
FEE_FLOOR_CEILINGS = [0.10, 0.15, 0.20, 0.25, 0.30]


# ── Data loading ──────────────────────────────────────────────────────────────

def _load_csv(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return [
        {
            "time":   r["time"],
            "open":   float(r["open"]),
            "high":   float(r["high"]),
            "low":    float(r["low"]),
            "close":  float(r["close"]),
            "volume": float(r.get("volume", 0) or 0),
        }
        for r in rows
    ]


def _utc(t) -> datetime:
    if isinstance(t, datetime):
        return t if t.tzinfo else t.replace(tzinfo=_UTC)
    s = str(t).replace("Z", "+00:00").replace(" ", "T")
    return datetime.fromisoformat(s)


def _ts(dt: datetime) -> str:
    """Format datetime → canonical ISO string matching CSV format."""
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


# ── Augmented signal ──────────────────────────────────────────────────────────

@dataclass
class AugSig:
    """Signal with session context needed for post-hoc variant filters."""
    signal: object        # Signal from run_strategy()
    symbol: str
    session: str          # 'london' | 'new_york'
    ctx_m15: list         # PRE_SESSION_BARS + SESSION_BARS bars (for Variant D)
    sweep_idx: int        # index in ctx_m15 of sweep bar (-1 = not found)
    h4_before: list       # 4H bars closed before sweep bar (for Variant C)
    h1_before: list       # 1H bars closed before sweep bar (empty if no H1 data)


def _extract_sweep_times(events: list[dict]) -> dict:
    """Parse run_strategy() debug events → {(date, session): sweep_time_iso}."""
    sweeps = {}
    for ev in events:
        if ev["event"] != "SWEEP":
            continue
        date   = ev["date"]   # "YYYY-MM-DD"
        detail = ev["detail"]
        m_sess = re.search(r"\] (\w+) side=", detail)
        m_time = re.search(r"\[(\d{2}:\d{2}) UTC\]", detail)
        if m_sess and m_time:
            sweeps[(date, m_sess.group(1))] = f"{date}T{m_time.group(1)}:00Z"
    return sweeps


def _find_session_start(sorted_m15: list[dict], from_idx: int, session: str) -> int:
    """
    Scan backwards from from_idx to find the first bar of `session`.
    Returns the index of the session's opening bar.
    """
    # Walk backwards at most SESSION_BARS + 5 bars (session is ≤ 12 bars wide)
    low = max(-1, from_idx - SESSION_BARS - 4)
    for j in range(from_idx, low, -1):
        if classify_session(_utc(sorted_m15[j]["time"])) != session:
            return j + 1
    # All scanned bars were in the session; return scan start
    return max(0, low + 1)


def _build_aug_signals(
    symbol: str,
    all_m15: list[dict],
    all_4h: list[dict],
    all_1h: list[dict],
    rr: float,
) -> list[AugSig]:
    """
    Run run_strategy() and augment each signal with session context for C and D.
    RR passed here only affects signal.take_profit (irrelevant: simulation recomputes).
    """
    signals, events = run_strategy(
        all_m15, all_4h, symbol, config={"rr": rr}, debug=True
    )
    sweep_times = _extract_sweep_times(events)

    sorted_m15 = sorted(all_m15, key=lambda c: c["time"])
    sorted_4h  = sorted(all_4h,  key=lambda c: c["time"])
    sorted_1h  = sorted(all_1h,  key=lambda c: c["time"]) if all_1h else []

    m15_idx = {c["time"]: i for i, c in enumerate(sorted_m15)}

    result: list[AugSig] = []
    for sig in signals:
        date_str   = _ts(sig.timestamp)[:10]
        sweep_iso  = sweep_times.get((date_str, sig.session), "")
        sweep_bar_global = m15_idx.get(sweep_iso, -1)

        # Find session start by scanning back from sweep bar (or signal bar)
        ref_bar_global = sweep_bar_global if sweep_bar_global >= 0 else m15_idx.get(_ts(sig.timestamp), -1)
        if ref_bar_global >= 0:
            sess_start = _find_session_start(sorted_m15, ref_bar_global, sig.session)
        else:
            sess_start = 0

        # ctx_m15 = PRE_SESSION_BARS pre-session bars + SESSION_BARS session bars.
        # The extra history gives CHoCH lookback and BOS swing detection enough
        # context when the sweep falls at the very first session bar.
        ctx_start   = max(0, sess_start - PRE_SESSION_BARS)
        ctx_m15     = sorted_m15[ctx_start : sess_start + SESSION_BARS]

        # Sweep index within ctx_m15
        sweep_idx_local = -1
        if sweep_bar_global >= 0:
            local = sweep_bar_global - ctx_start
            if 0 <= local < len(ctx_m15):
                sweep_idx_local = local

        # H4 / H1 slices: bars whose close time <= sweep bar time
        # close_time = open_time + Nh → include if open_time <= cutoff - Nh
        ref_dt = _utc(sweep_iso) if sweep_iso else sig.timestamp
        cutoff_4h = ref_dt - timedelta(hours=4)
        h4_before = [c for c in sorted_4h if _utc(c["time"]) <= cutoff_4h]

        if sorted_1h:
            cutoff_1h = ref_dt - timedelta(hours=1)
            h1_before = [c for c in sorted_1h if _utc(c["time"]) <= cutoff_1h]
        else:
            h1_before = []

        result.append(AugSig(
            signal=sig,
            symbol=symbol,
            session=sig.session,
            ctx_m15=ctx_m15,
            sweep_idx=sweep_idx_local,
            h4_before=h4_before,
            h1_before=h1_before,
        ))

    return result


# ── Variant filters ───────────────────────────────────────────────────────────

def _filter_A(sigs: list[AugSig]) -> list[AugSig]:
    """Exclude GBPUSD London."""
    return [s for s in sigs if not (s.symbol == "GBPUSD" and s.session == "london")]


def _filter_B(sigs: list[AugSig]) -> list[AugSig]:
    """NY only — drop all London signals."""
    return [s for s in sigs if s.session == "new_york"]


def _filter_C(sigs: list[AugSig]) -> list[AugSig]:
    """
    Strict HTF bias: 4H+1H structure at swing_n=3 must agree with signal direction.

    If H1 data is absent, uses 4H-only with swing_n=3 (htf_bias returns neutral
    from empty 1H list → 4H result passes through unchanged).
    """
    out = []
    for s in sigs:
        if not s.h4_before:
            continue
        expected = "bullish" if s.signal.side == "long" else "bearish"
        if htf_bias_combined(s.h4_before, s.h1_before, swing_n=3) == expected:
            out.append(s)
    return out


def _filter_D(sigs: list[AugSig]) -> list[AugSig]:
    """
    15M CHoCH+BOS gate between sweep and displacement/entry bar.

    CHoCH: first 15M close that breaks the pre-sweep reference level.
    BOS:   first 15M close that breaks the last confirmed swing before the sweep.
    Both must complete before the entry (displacement) bar in ctx_m15.
    Entry/SL/TP are unchanged — this is a pure inclusion gate.

    ctx_m15 includes PRE_SESSION_BARS of pre-session history so CHoCH lookback
    and BOS swing detection have enough bars even when the sweep is at bar 0 of
    the session (the sweep_idx field is already indexed into ctx_m15).
    """
    out = []
    for s in sigs:
        if s.sweep_idx < 0:
            continue

        ctx = s.ctx_m15
        direction = "bullish" if s.signal.side == "long" else "bearish"

        choch = detect_choch(ctx, s.sweep_idx, direction, CHOCH_LOOKBACK)
        if choch is None:
            continue

        if direction == "bullish":
            sw = last_swing_high(ctx, BOS_SWING_N, before_idx=s.sweep_idx)
        else:
            sw = last_swing_low(ctx, BOS_SWING_N, before_idx=s.sweep_idx)
        bos = detect_bos(ctx, choch["index"], direction, sw["price"] if sw else None)
        if bos is None:
            continue

        # Locate entry bar (displacement close) in ctx_m15
        entry_ts = _ts(s.signal.timestamp)
        entry_idx: Optional[int] = None
        for si, sc in enumerate(ctx):
            if sc["time"] == entry_ts:
                entry_idx = si
                break
        if entry_idx is None:
            # Fallback: match within 60s
            for si, sc in enumerate(ctx):
                if abs((_utc(sc["time"]) - s.signal.timestamp).total_seconds()) < 60:
                    entry_idx = si
                    break
        if entry_idx is None:
            continue

        # BOS must precede the entry (no lookahead)
        if bos["index"] < entry_idx:
            out.append(s)

    return out


def _fee_cost_r(symbol: str, sl_pips: float) -> float:
    """Standard spread RT expressed as fraction of 1R."""
    if sl_pips <= 0:
        return float("inf")
    return SPREAD[symbol]["standard"] / sl_pips


def _filter_E(sigs: list[AugSig], ceiling: float) -> list[AugSig]:
    """
    Fee-floor: keep only signals where standard spread cost R <= ceiling.
    Eliminates trades with stops so tight that spread eats the edge.
    """
    out = []
    for s in sigs:
        sl_pips = abs(s.signal.entry - s.signal.stop_loss) / _PIP
        if _fee_cost_r(s.symbol, sl_pips) <= ceiling:
            out.append(s)
    return out


# ── Trade simulation ──────────────────────────────────────────────────────────

def _simulate_all(
    aug_sigs: list[AugSig],
    m15_by_sym: dict,
    time_idx_by_sym: dict,
    rr: float,
) -> list[dict]:
    """
    Simulate each signal forward on the full M15 bars (up to MAX_SIM_BARS=96).
    Matches the simulation in scripts/backtest_session_liquidity.py exactly:
      - SL checked before TP on the same bar
      - Entry at displacement candle close; first scanned bar is the next one
      - Timeout: close at last bar, fractional R
    """
    trades = []
    for s in aug_sigs:
        sig = s.signal
        sym = s.symbol
        ts  = _ts(sig.timestamp)

        idx = time_idx_by_sym[sym].get(ts)
        if idx is None:
            continue

        bars   = m15_by_sym[sym]
        future = bars[idx + 1 : idx + 1 + MAX_SIM_BARS]
        entry  = float(sig.entry)
        sl     = float(sig.stop_loss)
        risk   = abs(entry - sl)
        if risk == 0:
            continue
        sl_pips = risk / _PIP
        tp = entry + risk * rr if sig.side == "long" else entry - risk * rr

        is_long  = sig.side == "long"
        gross_r  = 0.0
        exit_p   = entry
        exit_t   = ts

        hit = False
        for bar in future:
            h, lo = bar["high"], bar["low"]
            if is_long:
                if lo <= sl:
                    gross_r, exit_p, exit_t = -1.0, sl, bar["time"]
                    hit = True; break
                if h >= tp:
                    gross_r, exit_p, exit_t = rr, tp, bar["time"]
                    hit = True; break
            else:
                if h >= sl:
                    gross_r, exit_p, exit_t = -1.0, sl, bar["time"]
                    hit = True; break
                if lo <= tp:
                    gross_r, exit_p, exit_t = rr, tp, bar["time"]
                    hit = True; break

        if not hit and future:
            last    = future[-1]
            exit_p  = last["close"]
            exit_t  = last["time"]
            delta   = (exit_p - entry) if is_long else (entry - exit_p)
            gross_r = delta / risk

        sp_std = SPREAD[sym]["standard"]
        sp_2x  = SPREAD[sym]["2x"]

        trades.append({
            "symbol":    sym,
            "session":   sig.session,
            "side":      sig.side,
            "entry_t":   ts,
            "exit_t":    exit_t,
            "gross_r":   gross_r,
            "net_r_std": gross_r - sp_std / sl_pips,
            "net_r_2x":  gross_r - sp_2x  / sl_pips,
            "sl_pips":   sl_pips,
            "aug":       s,
        })

    return trades


# ── Metrics ───────────────────────────────────────────────────────────────────

def _metrics(trades: list[dict], r_key: str) -> dict:
    if not trades:
        return {"n": 0, "pf": 0.0, "win_rate": 0.0, "avg_r": 0.0, "max_dd": 0.0}

    rs       = [t[r_key] for t in trades]
    wins     = [r for r in rs if r > 0]
    losses   = [r for r in rs if r <= 0]
    gw       = sum(wins)
    gl       = abs(sum(losses))
    pf       = gw / gl if gl > 0 else (float("inf") if gw > 0 else 1.0)

    eq = peak = max_dd = 0.0
    for r in rs:
        eq += r
        if eq > peak:
            peak = eq
        dd = peak - eq
        if dd > max_dd:
            max_dd = dd

    return {
        "n":        len(trades),
        "pf":       round(pf, 3),
        "win_rate": round(len(wins) / len(trades), 4) if trades else 0.0,
        "avg_r":    round(sum(rs) / len(trades), 4) if trades else 0.0,
        "max_dd":   round(max_dd, 2),
    }


def _all_targets_pass(m2x: dict, m_std: dict, n_min: int) -> bool:
    return (
        m2x["pf"]           > TARGETS["pf_2x"]
        and m_std["win_rate"] >= TARGETS["win_rate"]
        and m_std["max_dd"]   < TARGETS["max_dd"]
        and m_std["n"]        >= n_min
    )


def _gates(m2x: dict, m_std: dict, n_min: int) -> dict:
    return {
        "n":    m_std["n"] >= n_min,
        "pf2x": m2x["pf"] > TARGETS["pf_2x"],
        "wr":   m_std["win_rate"] >= TARGETS["win_rate"],
        "dd":   m_std["max_dd"] < TARGETS["max_dd"],
        "all":  _all_targets_pass(m2x, m_std, n_min),
    }


# ── Report helpers ────────────────────────────────────────────────────────────

def _pf(v: float) -> str:
    return "∞" if v == float("inf") else f"{v:.3f}"


def _breakdown_table(trades: list[dict], r_key: str, group_key: str) -> list[tuple]:
    """[(group_name, n, pf, win_rate_pct), ...]"""
    groups: dict[str, list] = {}
    for t in trades:
        groups.setdefault(t[group_key], []).append(t)
    rows = []
    for name in sorted(groups):
        m = _metrics(groups[name], r_key)
        rows.append((name, m["n"], m["pf"], m["win_rate"] * 100))
    return rows


# ── Per-variant report ────────────────────────────────────────────────────────

def _write_variant(
    vid: str,
    trades: list[dict],
    sig_count: int,
    base_count: int,
    filter_desc: str,
    n_min: int,
) -> None:
    m_std = _metrics(trades, "net_r_std")
    m_2x  = _metrics(trades, "net_r_2x")
    g     = _gates(m_2x, m_std, n_min)

    wr_pct  = f"{m_std['win_rate'] * 100:.1f}%"
    tgt_wr  = f"{TARGETS['win_rate'] * 100:.0f}%"

    lines = [
        f"# EXP05_{vid}_RESULTS.md",
        f"# ST-A2 Optimization — Variant {vid}",
        "",
        f"**Filter:** {filter_desc}",
        f"**Signals:** {sig_count} of {base_count} baseline",
        f"**Trades:**  {m_std['n']}",
        "",
        "---",
        "",
        "## Metrics",
        "",
        "| Metric | Standard | 2× Stress | Target | Pass? |",
        "|---|---|---|---|---|",
        f"| n | {m_std['n']} | — | ≥ {n_min} | {'✅' if g['n'] else '❌'} |",
        f"| PF | {_pf(m_std['pf'])} | {_pf(m_2x['pf'])} | PF₂ₓ > {TARGETS['pf_2x']} | {'✅' if g['pf2x'] else '❌'} |",
        f"| Win Rate | {wr_pct} | — | ≥ {tgt_wr} | {'✅' if g['wr'] else '❌'} |",
        f"| Avg R | {m_std['avg_r']:.4f} | {m_2x['avg_r']:.4f} | — | — |",
        f"| Max DD (R) | {m_std['max_dd']:.2f} | {m_2x['max_dd']:.2f} | < {TARGETS['max_dd']} | {'✅' if g['dd'] else '❌'} |",
        "",
        f"**VERDICT: {'✅ PASS' if g['all'] else '❌ FAIL'}**",
        "",
        "---",
        "",
        "## Session Breakdown (standard spread)",
        "",
        "| Session | n | PF | Win% |",
        "|---|---|---|---|",
    ]
    for name, n, pf_val, wr in _breakdown_table(trades, "net_r_std", "session"):
        lines.append(f"| {name} | {n} | {_pf(pf_val)} | {wr:.1f}% |")

    lines += [
        "",
        "## Symbol Breakdown (standard spread)",
        "",
        "| Symbol | n | PF | Win% |",
        "|---|---|---|---|",
    ]
    for name, n, pf_val, wr in _breakdown_table(trades, "net_r_std", "symbol"):
        lines.append(f"| {name} | {n} | {_pf(pf_val)} | {wr:.1f}% |")

    (OUT_DIR / f"EXP05_{vid}_RESULTS.md").write_text("\n".join(lines) + "\n")


# ── Final comparison ──────────────────────────────────────────────────────────

def _write_comparison(
    base_trades: list[dict],
    variant_trades: dict,       # {vid: trades}
    e_sweep: dict,              # {ceiling: trades}
    best_e_seed_vid: str,
    rr: float,
) -> None:
    bm = _metrics(base_trades, "net_r_std")
    b2 = _metrics(base_trades, "net_r_2x")

    lines = [
        "# EXP05_FINAL_COMPARISON.md",
        f"# ST-A2 Optimization — Variant Comparison | RR={rr}",
        "",
        "| Variant | n | PF (std) | PF (2×) | Win% | Max DD | Δn | ΔPF₂ₓ |",
        "|---|---|---|---|---|---|---|---|",
        (
            f"| Baseline | {bm['n']} | {_pf(bm['pf'])} | {_pf(b2['pf'])} "
            f"| {bm['win_rate']*100:.1f}% | {bm['max_dd']:.2f} | — | — |"
        ),
    ]

    for vid in ["A", "B", "C", "D", "E"]:
        t  = variant_trades[vid]
        ms = _metrics(t, "net_r_std")
        m2 = _metrics(t, "net_r_2x")
        dn = ms["n"] - bm["n"]
        dp = (m2["pf"] - b2["pf"]) if b2["pf"] != float("inf") else float("inf")
        lines.append(
            f"| {vid} | {ms['n']} | {_pf(ms['pf'])} | {_pf(m2['pf'])} "
            f"| {ms['win_rate']*100:.1f}% | {ms['max_dd']:.2f} "
            f"| {dn:+d} | {dp:+.3f} |"
        )

    lines += [
        "",
        f"## Variant E — Fee-Floor Sweep (seed: Variant {best_e_seed_vid})",
        "",
        "| Ceiling | n removed | n kept | PF (std) | PF (2×) | Win% | Max DD |",
        "|---|---|---|---|---|---|---|",
    ]
    seed_n = _metrics(variant_trades.get(best_e_seed_vid, base_trades), "net_r_std")["n"]
    for ceiling, et in sorted(e_sweep.items()):
        ms = _metrics(et, "net_r_std")
        m2 = _metrics(et, "net_r_2x")
        lines.append(
            f"| {ceiling:.2f} | {seed_n - ms['n']:+d} | {ms['n']} "
            f"| {_pf(ms['pf'])} | {_pf(m2['pf'])} "
            f"| {ms['win_rate']*100:.1f}% | {ms['max_dd']:.2f} |"
        )

    (OUT_DIR / "EXP05_FINAL_COMPARISON.md").write_text("\n".join(lines) + "\n")


# ── Recommendation ────────────────────────────────────────────────────────────

def _write_recommendation(
    base_trades: list[dict],
    variant_trades: dict,   # {vid: trades}
    rr: float,
    n_min: int,
) -> None:
    bm = _metrics(base_trades, "net_r_std")
    b2 = _metrics(base_trades, "net_r_2x")

    lines = [
        "# EXP05_RECOMMENDATION.md",
        "# EXP05 Mechanical PASS/FAIL — No Opinion Added",
        f"# RR = {rr}",
        "",
        "---",
        "",
        "## Baseline",
        f"n={bm['n']} | PF (std)={_pf(bm['pf'])} | PF (2×)={_pf(b2['pf'])} "
        f"| WR={bm['win_rate']*100:.1f}% | MaxDD={bm['max_dd']:.2f}R",
        "",
        "## EXP05 Targets (all four must hold)",
        "",
        f"| Gate | Target |",
        f"|---|---|",
        f"| PF (2× spread) | > {TARGETS['pf_2x']} |",
        f"| Win Rate | > {TARGETS['win_rate']*100:.0f}% |",
        f"| Max DD | < {TARGETS['max_dd']}R |",
        f"| n | ≥ {n_min} |",
        "",
        "## Variant Verdicts",
        "",
        "| Variant | n | PF₂ₓ | WR% | Max DD | VERDICT |",
        "|---|---|---|---|---|---|",
    ]

    passing = []
    for vid in ["A", "B", "C", "D", "E"]:
        t  = variant_trades[vid]
        ms = _metrics(t, "net_r_std")
        m2 = _metrics(t, "net_r_2x")
        g  = _all_targets_pass(m2, ms, n_min)
        if g:
            passing.append((vid, m2["pf"], ms["n"]))
        lines.append(
            f"| {vid} | {ms['n']} | {_pf(m2['pf'])} "
            f"| {ms['win_rate']*100:.1f}% | {ms['max_dd']:.2f} "
            f"| {'✅ PASS' if g else '❌ FAIL'} |"
        )

    lines += ["", "---", ""]

    if passing:
        best = max(passing, key=lambda x: x[1])
        lines += [
            "## Outcome: ✅ AT LEAST ONE VARIANT PASSES",
            "",
            f"Best variant by PF₂ₓ: **{best[0]}** (n={best[2]}, PF₂ₓ={_pf(best[1])})",
            "",
            "Next steps (per CLAUDE.md §9 / §3):",
            "1. Register the winning variant as a new trial in docs/VERDICT_LOG.md.",
            "2. Deploy the filter in the production signal chain.",
            "3. Re-run Phase-0 backtest on the new trial to confirm gate.",
            "4. If confirmed: proceed to Phase-1 demo trading.",
        ]
    else:
        lines += [
            "## Outcome: ❌ NO VARIANT PASSES ALL TARGETS",
            "",
            "Per EXP05 §1: FAIL → begin Strategy B research.",
            "Register FAIL in docs/VERDICT_LOG.md.",
        ]

    (OUT_DIR / "EXP05_RECOMMENDATION.md").write_text("\n".join(lines) + "\n")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="EXP05 optimization runner")
    parser.add_argument("--rr",         type=float, default=5.0,
                        help="RR for simulation (default 5.0 — passing ST-A2 RR)")
    parser.add_argument("--min-trades", type=int,   default=100,
                        dest="min_trades")
    args   = parser.parse_args()
    rr     = args.rr
    n_min  = args.min_trades
    TARGETS["n_min"] = n_min

    print(f"\n=== EXP05 Optimization Runner | RR={rr} | min-trades={n_min} ===\n")

    # ── Required file check (exit 2 on missing) ──────────────────────────────
    missing = []
    for sym in SYMBOLS:
        for label, tbl in [("M15", _M15), ("H4", _H4)]:
            p = DATA_DIR / tbl[sym]
            if not p.exists():
                missing.append(f"{sym} {label}: {p}")
    if missing:
        print("ERROR: required data files are missing:")
        for m in missing:
            print(f"  {m}")
        print("\nFix: python3 scripts/fetch_data.py --symbols EURUSD GBPUSD")
        sys.exit(2)

    # ── Load data ─────────────────────────────────────────────────────────────
    print("[+] Loading data ...")
    m15_by_sym: dict[str, list[dict]] = {}
    h4_by_sym:  dict[str, list[dict]] = {}
    h1_by_sym:  dict[str, list[dict]] = {}
    tidx:       dict[str, dict]       = {}

    for sym in SYMBOLS:
        m15 = _load_csv(DATA_DIR / _M15[sym])
        m15.sort(key=lambda c: c["time"])
        m15_by_sym[sym] = m15
        tidx[sym]       = {c["time"]: i for i, c in enumerate(m15)}

        h4 = _load_csv(DATA_DIR / _H4[sym])
        h4.sort(key=lambda c: c["time"])
        h4_by_sym[sym] = h4

        h1_path = DATA_DIR / _H1[sym]
        if h1_path.exists():
            h1 = _load_csv(h1_path)
            h1.sort(key=lambda c: c["time"])
            h1_by_sym[sym] = h1
            h1_label = f"{len(h1):,} H1"
        else:
            h1_by_sym[sym] = []
            h1_label = "H1=none (Variant C uses 4H only)"

        print(f"    {sym}: {len(m15):,} M15 | {len(h4):,} H4 | {h1_label}")

    # ── Generate baseline signals ─────────────────────────────────────────────
    print("\n[+] Generating baseline signals ...")
    all_aug: list[AugSig] = []
    for sym in SYMBOLS:
        print(f"    {sym} ...", end=" ", flush=True)
        aug = _build_aug_signals(sym, m15_by_sym[sym], h4_by_sym[sym], h1_by_sym[sym], rr)
        all_aug.extend(aug)
        print(f"{len(aug)} signals")
    print(f"    Baseline total: {len(all_aug)} signals")

    # ── Simulate baseline ─────────────────────────────────────────────────────
    print("\n[+] Simulating baseline trades ...")
    base_trades = _simulate_all(all_aug, m15_by_sym, tidx, rr)
    bm = _metrics(base_trades, "net_r_std")
    b2 = _metrics(base_trades, "net_r_2x")
    print(f"    n={bm['n']} | PF_std={_pf(bm['pf'])} | PF_2x={_pf(b2['pf'])} "
          f"| WR={bm['win_rate']*100:.1f}% | MaxDD={bm['max_dd']:.2f}R")
    print(f"    (Documented baseline: n=169 | PF_2x=1.025 at RR=5)")

    # ── Apply variant filters ─────────────────────────────────────────────────
    print("\n[+] Applying variant filters ...")
    va_sigs = _filter_A(all_aug)
    vb_sigs = _filter_B(all_aug)
    vc_sigs = _filter_C(vb_sigs)
    vd_sigs = _filter_D(vc_sigs)

    print(f"    A (excl GBPUSD London): {len(va_sigs)} signals from {len(all_aug)}")
    print(f"    B (NY only):            {len(vb_sigs)} signals")
    print(f"    C (B + strict bias):    {len(vc_sigs)} signals from {len(vb_sigs)} B")
    print(f"    D (C + CHoCH+BOS):      {len(vd_sigs)} signals from {len(vc_sigs)} C")

    # ── Simulate A-D ─────────────────────────────────────────────────────────
    print("\n[+] Simulating A-D ...")
    va_trades = _simulate_all(va_sigs, m15_by_sym, tidx, rr)
    vb_trades = _simulate_all(vb_sigs, m15_by_sym, tidx, rr)
    vc_trades = _simulate_all(vc_sigs, m15_by_sym, tidx, rr)
    vd_trades = _simulate_all(vd_sigs, m15_by_sym, tidx, rr)

    for vid, t in [("A", va_trades), ("B", vb_trades), ("C", vc_trades), ("D", vd_trades)]:
        ms = _metrics(t, "net_r_std")
        m2 = _metrics(t, "net_r_2x")
        g  = "✅" if _all_targets_pass(m2, ms, n_min) else "❌"
        print(f"    {vid}: n={ms['n']:3d} PF_std={_pf(ms['pf'])} PF_2x={_pf(m2['pf'])} "
              f"WR={ms['win_rate']*100:4.1f}% DD={ms['max_dd']:.2f}R  {g}")

    # ── Variant E: fee-floor sweep on best-PF₂ₓ seed ─────────────────────────
    candidates = {
        "Baseline": (all_aug, base_trades),
        "A": (va_sigs, va_trades),
        "B": (vb_sigs, vb_trades),
        "C": (vc_sigs, vc_trades),
        "D": (vd_sigs, vd_trades),
    }
    best_seed = max(
        candidates,
        key=lambda k: _metrics(candidates[k][1], "net_r_2x")["pf"]
    )
    seed_sigs = candidates[best_seed][0]
    print(f"\n[+] Variant E seed: {best_seed} (highest PF₂ₓ)")

    e_sweep: dict[float, list[dict]] = {}
    best_e_pf2x = -1.0
    best_e_trades: list[dict] = []
    best_e_sigs: list[AugSig] = []

    for ceiling in FEE_FLOOR_CEILINGS:
        e_sigs   = _filter_E(seed_sigs, ceiling)
        e_trades = _simulate_all(e_sigs, m15_by_sym, tidx, rr)
        e_sweep[ceiling] = e_trades
        m2 = _metrics(e_trades, "net_r_2x")
        if m2["pf"] > best_e_pf2x:
            best_e_pf2x    = m2["pf"]
            best_e_trades  = e_trades
            best_e_sigs    = e_sigs
        ms = _metrics(e_trades, "net_r_std")
        g  = "✅" if _all_targets_pass(m2, ms, n_min) else "❌"
        print(f"    E ceiling={ceiling:.2f}: n={ms['n']:3d} PF_2x={_pf(m2['pf'])} "
              f"WR={ms['win_rate']*100:.1f}%  {g}")

    # ── Collect all variants ──────────────────────────────────────────────────
    variant_trades = {
        "A": va_trades,
        "B": vb_trades,
        "C": vc_trades,
        "D": vd_trades,
        "E": best_e_trades,
    }
    variant_sigs = {
        "A": va_sigs,
        "B": vb_sigs,
        "C": vc_sigs,
        "D": vd_sigs,
        "E": best_e_sigs,
    }

    # ── Write reports ─────────────────────────────────────────────────────────
    print("\n[+] Writing reports to research/ ...")
    OUT_DIR.mkdir(exist_ok=True)

    filter_descs = {
        "A": "Exclude GBPUSD London",
        "B": "NY only (exclude all London)",
        "C": "NY only + strict HTF bias (swing_n=3 + 1H agreement where H1 present)",
        "D": "NY only + strict bias + 15M CHoCH+BOS gate between sweep and entry",
        "E": f"Fee-floor on Variant {best_seed} (best-PF₂ₓ ceiling from sweep 0.10–0.30)",
    }
    for vid in ["A", "B", "C", "D", "E"]:
        _write_variant(
            vid, variant_trades[vid],
            len(variant_sigs[vid]), len(all_aug),
            filter_descs[vid], n_min,
        )

    _write_comparison(base_trades, variant_trades, e_sweep, best_seed, rr)
    _write_recommendation(base_trades, variant_trades, rr, n_min)

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n=== EXP05 Summary ===\n")
    print(f"  {'Variant':<10} {'n':>5} {'PF (std)':>9} {'PF (2×)':>9} "
          f"{'WR%':>7} {'MaxDD':>7}  Result")
    print(f"  {'─' * 60}")

    bm = _metrics(base_trades, "net_r_std")
    b2 = _metrics(base_trades, "net_r_2x")
    print(f"  {'Baseline':<10} {bm['n']:>5} {_pf(bm['pf']):>9} {_pf(b2['pf']):>9} "
          f"{bm['win_rate']*100:>6.1f}% {bm['max_dd']:>7.2f}  (reference)")

    for vid in ["A", "B", "C", "D", "E"]:
        t  = variant_trades[vid]
        ms = _metrics(t, "net_r_std")
        m2 = _metrics(t, "net_r_2x")
        g  = "✅ PASS" if _all_targets_pass(m2, ms, n_min) else "❌ FAIL"
        print(f"  {vid:<10} {ms['n']:>5} {_pf(ms['pf']):>9} {_pf(m2['pf']):>9} "
              f"{ms['win_rate']*100:>6.1f}% {ms['max_dd']:>7.2f}  {g}")

    print(f"\n  Outputs → research/EXP05_*.md\n")


if __name__ == "__main__":
    main()
