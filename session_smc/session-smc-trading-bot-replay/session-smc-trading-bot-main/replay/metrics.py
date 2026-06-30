"""
replay/metrics.py — Statistics and gate evaluation for replay results.

Computes per-strategy, per-symbol, per-year, per-session breakdowns.
Evaluates the demo gate: minimum trades + profit factor at standard and 2× stress spread.

Public API:
    compute_metrics(net_rs)             → MetricSet
    strategy_report(trades, r_key)      → dict[strategy → MetricSet]
    breakdown(trades, group_fn, r_key)  → dict[group_key → MetricSet]
    gate_check(trades)                  → GateResult
    print_summary(result, gate)         → None
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from replay.engine import ReplayTrade

# ── Gate thresholds ───────────────────────────────────────────────────────────

GATE_MIN_TRADES: dict[str, int] = {
    "ST-A2":         50,   # already validated — reconfirm
    "LondonBreakout": 30,
    "NYMomentum":     30,
    "AdaptiveSMC":    20,  # shadow — informational only
    "VWAPBreakout":   20,  # shadow — informational only
}
GATE_MIN_PF_STD    = 1.0
GATE_MIN_PF_STRESS = 1.0
GATE_MIN_WIN_RATE  = 0.35   # 35% minimum — strategies rely on high RR

# ── Metric dataclass ──────────────────────────────────────────────────────────

@dataclass
class MetricSet:
    n:           int
    wins:        int
    losses:      int
    timeouts:    int
    win_rate:    float   # 0.0–1.0
    avg_r:       float
    total_r:     float
    pf:          float   # profit factor (gross wins / gross losses)
    max_dd_r:    float   # peak-to-trough in R units
    expectancy:  float   # avg_r (same, alias for clarity)

    def pf_str(self) -> str:
        return "∞" if self.pf == float("inf") else f"{self.pf:.3f}"

    def win_pct(self) -> str:
        return f"{self.win_rate * 100:.1f}%"


# ── Core computation ──────────────────────────────────────────────────────────

def compute_metrics(net_rs: list[float], exit_reasons: list[str] | None = None) -> MetricSet:
    """Compute MetricSet from a list of net-R outcomes."""
    if not net_rs:
        return MetricSet(0, 0, 0, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    reasons = exit_reasons or [""] * len(net_rs)
    wins    = [r for r in net_rs if r > 0]
    losses  = [r for r in net_rs if r <= 0]
    tos     = sum(1 for r in reasons if r == "TIMEOUT")

    gross_wins   = sum(wins)
    gross_losses = abs(sum(losses))

    if gross_losses == 0:
        pf = float("inf") if gross_wins > 0 else 1.0
    elif gross_wins == 0:
        pf = 0.0
    else:
        pf = gross_wins / gross_losses

    # Peak-to-trough drawdown in R
    equity = peak = max_dd = 0.0
    for r in net_rs:
        equity += r
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)

    avg_r = sum(net_rs) / len(net_rs)
    return MetricSet(
        n        = len(net_rs),
        wins     = len(wins),
        losses   = len(losses),
        timeouts = tos,
        win_rate = len(wins) / len(net_rs),
        avg_r    = round(avg_r, 4),
        total_r  = round(sum(net_rs), 4),
        pf       = round(pf, 4) if pf != float("inf") else float("inf"),
        max_dd_r = round(max_dd, 4),
        expectancy = round(avg_r, 4),
    )


# ── Grouping helpers ──────────────────────────────────────────────────────────

def breakdown(
    trades: list[ReplayTrade],
    group_fn: Callable[[ReplayTrade], str],
    r_key: str = "net_r_std",
) -> dict[str, MetricSet]:
    """Group trades by group_fn and compute MetricSet for each group."""
    groups: dict[str, list[ReplayTrade]] = {}
    for t in trades:
        key = group_fn(t)
        groups.setdefault(key, []).append(t)
    return {
        k: compute_metrics(
            [getattr(t, r_key) for t in v],
            [t.exit_reason for t in v],
        )
        for k, v in sorted(groups.items())
    }


def strategy_report(
    trades: list[ReplayTrade],
    r_key: str = "net_r_std",
) -> dict[str, MetricSet]:
    return breakdown(trades, lambda t: t.strategy, r_key)


def symbol_report(
    trades: list[ReplayTrade],
    r_key: str = "net_r_std",
) -> dict[str, MetricSet]:
    return breakdown(trades, lambda t: t.symbol, r_key)


def year_report(
    trades: list[ReplayTrade],
    r_key: str = "net_r_std",
) -> dict[str, MetricSet]:
    return breakdown(trades, lambda t: t.entry_time[:4], r_key)


def session_report(
    trades: list[ReplayTrade],
    r_key: str = "net_r_std",
) -> dict[str, MetricSet]:
    return breakdown(trades, lambda t: t.session or "unknown", r_key)


def mode_report(
    trades: list[ReplayTrade],
    r_key: str = "net_r_std",
) -> dict[str, MetricSet]:
    return breakdown(trades, lambda t: t.mode, r_key)


# ── Gate evaluation ───────────────────────────────────────────────────────────

@dataclass
class StrategyGate:
    strategy:    str
    mode:        str           # "demo" | "shadow"
    n:           int
    pf_std:      float
    pf_stress:   float
    win_rate:    float
    pass_trade:  bool          # n >= min_trades
    pass_pf_std: bool          # pf >= GATE_MIN_PF_STD
    pass_pf_2x:  bool          # pf_stress >= GATE_MIN_PF_STRESS
    pass_wr:     bool          # win_rate >= GATE_MIN_WIN_RATE
    overall:     bool
    notes:       str


@dataclass
class GateResult:
    strategies: list[StrategyGate]

    @property
    def demo_ready(self) -> bool:
        """True if ALL demo strategies pass their gate."""
        demo = [s for s in self.strategies if s.mode == "demo"]
        return all(s.overall for s in demo)

    @property
    def shadow_ready(self) -> bool:
        """True if ALL shadow strategies have sufficient signals (informational)."""
        shadow = [s for s in self.strategies if s.mode == "shadow"]
        return all(s.pass_trade for s in shadow)


def gate_check(trades: list[ReplayTrade]) -> GateResult:
    """Evaluate demo/shadow gate for each strategy."""
    mode_map = {
        "ST-A2": "demo", "LondonBreakout": "demo", "NYMomentum": "demo",
        "AdaptiveSMC": "shadow", "VWAPBreakout": "shadow",
    }
    strategy_names = sorted({t.strategy for t in trades})
    gates: list[StrategyGate] = []

    for name in strategy_names:
        st_trades = [t for t in trades if t.strategy == name]
        mode = mode_map.get(name, "shadow")
        min_n = GATE_MIN_TRADES.get(name, 20)

        std_rs    = [t.net_r_std    for t in st_trades]
        stress_rs = [t.net_r_stress for t in st_trades]

        m_std    = compute_metrics(std_rs)
        m_stress = compute_metrics(stress_rs)

        p_trade  = m_std.n    >= min_n
        p_pf_std = m_std.pf   >= GATE_MIN_PF_STD    if m_std.n > 0 else False
        p_pf_2x  = m_stress.pf >= GATE_MIN_PF_STRESS if m_stress.n > 0 else False
        p_wr     = m_std.win_rate >= GATE_MIN_WIN_RATE if m_std.n > 0 else False

        if mode == "shadow":
            overall = p_trade   # shadow: just need enough signals to observe
            notes   = "Shadow — informational, no order gate"
        else:
            overall = p_trade and p_pf_std and p_pf_2x and p_wr
            notes_parts = []
            if not p_trade:
                notes_parts.append(f"need {min_n} trades (got {m_std.n})")
            if not p_pf_std:
                notes_parts.append(f"PF_std={m_std.pf_str()} < {GATE_MIN_PF_STD}")
            if not p_pf_2x:
                notes_parts.append(f"PF_2x={m_stress.pf_str()} < {GATE_MIN_PF_STRESS}")
            if not p_wr:
                notes_parts.append(f"WR={m_std.win_pct()} < {GATE_MIN_WIN_RATE*100:.0f}%")
            notes = "; ".join(notes_parts) if notes_parts else "All checks passed"

        gates.append(StrategyGate(
            strategy    = name,
            mode        = mode,
            n           = m_std.n,
            pf_std      = m_std.pf,
            pf_stress   = m_stress.pf,
            win_rate    = m_std.win_rate,
            pass_trade  = p_trade,
            pass_pf_std = p_pf_std,
            pass_pf_2x  = p_pf_2x,
            pass_wr     = p_wr,
            overall     = overall,
            notes       = notes,
        ))

    return GateResult(strategies=gates)


# ── Console summary printer ───────────────────────────────────────────────────

def print_summary(trades: list[ReplayTrade], gate: GateResult) -> None:
    """Print a full replay summary to stdout."""
    print(f"\n{'═'*68}")
    print("  REPLAY SUMMARY")
    print(f"{'═'*68}")

    # ── Per-strategy table ────────────────────────────────────────────────────
    print(f"\n  {'Strategy':<20} {'Mode':<8} {'N':>5} {'PF_std':>8} {'PF_2x':>8} "
          f"{'WR':>7} {'AvgR':>7} {'MaxDD':>7} {'Gate':>8}")
    print(f"  {'-'*68}")

    _mode_map = {
        "ST-A2": "demo", "LondonBreakout": "demo", "NYMomentum": "demo",
        "AdaptiveSMC": "shadow", "VWAPBreakout": "shadow",
    }

    for g in gate.strategies:
        st_trades  = [t for t in trades if t.strategy == g.strategy]
        std_rs     = [t.net_r_std    for t in st_trades]
        stress_rs  = [t.net_r_stress for t in st_trades]
        m_std      = compute_metrics(std_rs)
        m_stress   = compute_metrics(stress_rs)

        verdict = "✅ PASS" if g.overall else ("📋 OBS" if g.mode == "shadow" else "❌ FAIL")
        pf_s    = m_std.pf_str()
        pf_2x   = m_stress.pf_str()
        print(f"  {g.strategy:<20} {g.mode:<8} {m_std.n:>5} {pf_s:>8} {pf_2x:>8} "
              f"{m_std.win_pct():>7} {m_std.avg_r:>7.3f} {m_std.max_dd_r:>7.2f} {verdict:>8}")

    # ── Per-year breakdown (combined demo strategies) ─────────────────────────
    demo_trades = [t for t in trades if t.mode == "demo"]
    if demo_trades:
        print(f"\n  {'─'*68}")
        print("  Year breakdown (demo strategies, std spread)")
        print(f"  {'Year':<8} {'N':>5} {'PF':>8} {'WR':>7} {'AvgR':>7} {'TotalR':>8}")
        print(f"  {'─'*68}")
        yr_map = year_report(demo_trades, "net_r_std")
        for yr, m in sorted(yr_map.items()):
            flag = "  ⚠" if m.pf < 1.0 and m.n >= 5 else ""
            print(f"  {yr:<8} {m.n:>5} {m.pf_str():>8} {m.win_pct():>7} "
                  f"{m.avg_r:>7.3f} {m.total_r:>8.2f}{flag}")

    # ── Per-session breakdown ─────────────────────────────────────────────────
    if demo_trades:
        print("\n  Session breakdown (demo strategies, std spread)")
        print(f"  {'Session':<12} {'N':>5} {'PF':>8} {'WR':>7} {'AvgR':>7}")
        print(f"  {'─'*68}")
        sess_map = session_report(demo_trades, "net_r_std")
        for sess, m in sorted(sess_map.items()):
            print(f"  {sess:<12} {m.n:>5} {m.pf_str():>8} {m.win_pct():>7} {m.avg_r:>7.3f}")

    # ── Gate verdict ──────────────────────────────────────────────────────────
    print(f"\n  {'═'*68}")
    print("  GATE RESULTS")
    print(f"  {'─'*68}")
    for g in gate.strategies:
        icon = "✅" if g.overall else ("📋" if g.mode == "shadow" else "❌")
        print(f"  {icon}  {g.strategy:<20} {g.notes}")

    print(f"\n  {'─'*68}")
    if gate.demo_ready:
        print("  ✅ ALL DEMO STRATEGIES PASS — cleared for Vantage demo connection")
    else:
        failed = [g.strategy for g in gate.strategies if g.mode == "demo" and not g.overall]
        print(f"  ❌ DEMO GATE FAIL — {', '.join(failed)} did not pass")
    print(f"  {'═'*68}\n")
