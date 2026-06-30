"""
replay/exporter.py — Export replay results to CSV and Markdown.

Outputs:
    replay/results/replay_trades_<YYYYMMDD>.csv   — full trade log (one row per trade)
    replay/results/replay_report_<YYYYMMDD>.md    — human-readable summary + tables
    replay/results/replay_smoke_test.txt          — smoke test: signal count per strategy
"""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path

from replay.engine import ReplayResult
from replay.metrics import (
    GateResult, compute_metrics, year_report, session_report,
)

_RESULTS_DIR = Path(__file__).parent / "results"

_TRADE_FIELDS = [
    "strategy", "symbol", "mode", "action", "session",
    "entry_time", "exit_time", "exit_reason",
    "entry_price", "stop_loss", "take_profit", "exit_price",
    "sl_pips", "bars_held",
    "gross_r", "cost_r_std", "net_r_std", "net_r_stress",
    "risk_percent", "confidence",
]


def export_csv(result: ReplayResult, path: Path | None = None) -> Path:
    """Write full trade log to CSV. Returns path written."""
    _RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
    out = path or (_RESULTS_DIR / f"replay_trades_{today}.csv")

    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=_TRADE_FIELDS, extrasaction="ignore")
        w.writeheader()
        for t in result.trades:
            w.writerow({
                "strategy":    t.strategy,
                "symbol":      t.symbol,
                "mode":        t.mode,
                "action":      t.action,
                "session":     t.session,
                "entry_time":  t.entry_time,
                "exit_time":   t.exit_time,
                "exit_reason": t.exit_reason,
                "entry_price": t.entry_price,
                "stop_loss":   t.stop_loss,
                "take_profit": t.take_profit,
                "exit_price":  t.exit_price,
                "sl_pips":     t.sl_pips,
                "bars_held":   t.bars_held,
                "gross_r":     t.gross_r,
                "cost_r_std":  t.cost_r_std,
                "net_r_std":   t.net_r_std,
                "net_r_stress":t.net_r_stress,
                "risk_percent":t.risk_percent,
                "confidence":  t.confidence,
            })

    print(f"[+] Trades CSV  : {out}")
    return out


def _pf(v: float) -> str:
    return "∞" if v == float("inf") else f"{v:.3f}"


def _md_row(*cells) -> str:
    return "| " + " | ".join(str(c) for c in cells) + " |"


def _md_table(headers: list[str], rows: list[list]) -> list[str]:
    sep = ["-" * max(4, len(h)) for h in headers]
    lines = [_md_row(*headers), _md_row(*sep)]
    for r in rows:
        lines.append(_md_row(*r))
    return lines


def export_report(result: ReplayResult, gate: GateResult, path: Path | None = None) -> Path:
    """Write Markdown replay report. Returns path written."""
    _RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    cfg   = result.config
    today = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ts    = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
    out   = path or (_RESULTS_DIR / f"replay_report_{ts}.md")

    lines: list[str] = [
        "# Historical Replay Report",
        "",
        f"**Period:** {cfg.start} → {cfg.end}",
        f"**Symbols:** {', '.join(cfg.symbols)}",
        f"**Generated:** {today}",
        f"**Total signals:** {len(result.trades)}",
        "",
        "---",
        "",
        "## Gate Summary",
        "",
    ]

    # Gate table
    gate_headers = ["Strategy", "Mode", "N", "PF (std)", "PF (2×)", "WR", "Avg R", "Gate"]
    gate_rows = []
    for g in gate.strategies:
        st_trades = [t for t in result.trades if t.strategy == g.strategy]
        std_rs    = [t.net_r_std    for t in st_trades]
        stress_rs = [t.net_r_stress for t in st_trades]
        m_std     = compute_metrics(std_rs)
        m_stress  = compute_metrics(stress_rs)
        verdict   = "✅ PASS" if g.overall else ("📋 OBS" if g.mode == "shadow" else "❌ FAIL")
        gate_rows.append([
            g.strategy, g.mode, m_std.n,
            _pf(m_std.pf), _pf(m_stress.pf),
            m_std.win_pct(), f"{m_std.avg_r:.3f}", verdict,
        ])
    lines += _md_table(gate_headers, gate_rows)

    if gate.demo_ready:
        lines += ["", "**✅ ALL DEMO STRATEGIES PASS — cleared for Vantage demo connection**", ""]
    else:
        failed = [g.strategy for g in gate.strategies if g.mode == "demo" and not g.overall]
        lines += ["", f"**❌ DEMO GATE FAIL — {', '.join(failed)} did not pass**", ""]
        for g in gate.strategies:
            if g.mode == "demo" and not g.overall:
                lines.append(f"- **{g.strategy}**: {g.notes}")
        lines.append("")

    lines += ["---", "", "## Per-Strategy Detail", ""]

    strat_names = sorted({t.strategy for t in result.trades})
    for name in strat_names:
        st = [t for t in result.trades if t.strategy == name]
        std_rs    = [t.net_r_std    for t in st]
        stress_rs = [t.net_r_stress for t in st]
        gross_rs  = [t.gross_r      for t in st]
        m_std     = compute_metrics(std_rs,    [t.exit_reason for t in st])
        m_stress  = compute_metrics(stress_rs)
        m_gross   = compute_metrics(gross_rs)

        mode = st[0].mode if st else "?"
        lines += [f"### {name} ({mode})", ""]

        # Summary table
        metric_headers = ["Metric", "Standard spread", "2× Stress spread"]
        metric_rows = [
            ["Trades",      m_std.n, m_stress.n],
            ["Wins",        m_std.wins, m_stress.wins],
            ["Losses",      m_std.losses, m_stress.losses],
            ["Timeouts",    m_std.timeouts, "—"],
            ["Win rate",    m_std.win_pct(), m_stress.win_pct()],
            ["Avg R",       f"{m_std.avg_r:.3f}", f"{m_stress.avg_r:.3f}"],
            ["Profit factor",_pf(m_std.pf), _pf(m_stress.pf)],
            ["Max DD (R)",   f"{m_std.max_dd_r:.2f}", f"{m_stress.max_dd_r:.2f}"],
            ["Total R",     f"{m_std.total_r:.2f}", f"{m_stress.total_r:.2f}"],
        ]
        lines += _md_table(metric_headers, metric_rows)
        lines.append("")

        # Per-symbol
        syms = sorted({t.symbol for t in st})
        if len(syms) > 1:
            sym_headers = ["Symbol", "N", "PF (std)", "WR", "Avg R"]
            sym_rows = []
            for sym in syms:
                sym_ts  = [t for t in st if t.symbol == sym]
                m = compute_metrics([t.net_r_std for t in sym_ts])
                sym_rows.append([sym, m.n, _pf(m.pf), m.win_pct(), f"{m.avg_r:.3f}"])
            lines += ["**By symbol:**", ""] + _md_table(sym_headers, sym_rows) + [""]

        # Per-session
        sess_map = session_report(st, "net_r_std")
        if len(sess_map) > 1:
            sess_headers = ["Session", "N", "PF", "WR", "Avg R"]
            sess_rows = [[s, m.n, _pf(m.pf), m.win_pct(), f"{m.avg_r:.3f}"]
                         for s, m in sorted(sess_map.items())]
            lines += ["**By session:**", ""] + _md_table(sess_headers, sess_rows) + [""]

        # Per-year
        yr_map = year_report(st, "net_r_std")
        yr_headers = ["Year", "N", "PF (std)", "WR", "Avg R", "Total R"]
        yr_rows = []
        for yr, m in sorted(yr_map.items()):
            flag = " ⚠" if m.pf < 1.0 and m.n >= 5 else ""
            yr_rows.append([yr, m.n, _pf(m.pf) + flag, m.win_pct(), f"{m.avg_r:.3f}", f"{m.total_r:.2f}"])
        lines += ["**By year:**", ""] + _md_table(yr_headers, yr_rows) + [""]

    # Combined demo breakdown
    demo_trades = [t for t in result.trades if t.mode == "demo"]
    if demo_trades:
        lines += ["---", "", "## Combined Demo Portfolio", ""]
        yr_headers = ["Year", "N", "PF (std)", "WR", "Avg R", "Total R"]
        yr_rows = []
        for yr, m in sorted(year_report(demo_trades, "net_r_std").items()):
            flag = " ⚠" if m.pf < 1.0 and m.n >= 5 else ""
            yr_rows.append([yr, m.n, _pf(m.pf) + flag, m.win_pct(), f"{m.avg_r:.3f}", f"{m.total_r:.2f}"])
        lines += ["**Portfolio by year:**", ""] + _md_table(yr_headers, yr_rows) + [""]

    # Errors
    if result.errors:
        lines += ["---", "", "## Errors / Warnings", ""]
        for e in result.errors:
            lines.append(f"- `{e}`")
        lines.append("")

    lines.append(f"*Generated by replay/exporter.py at {today}*")

    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"[+] Report MD   : {out}")
    return out


def export_smoke_test(result: ReplayResult, path: Path | None = None) -> Path:
    """
    Write a quick smoke test summary — signal count per strategy per symbol.
    Zero signals = broken strategy, wrong data, bad config.
    """
    _RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
    out   = path or (_RESULTS_DIR / f"replay_smoke_{today}.txt")

    lines = [
        "Replay Smoke Test — Signal Counts",
        f"Period : {result.config.start} → {result.config.end}",
        f"Symbols: {', '.join(result.config.symbols)}",
        "",
        f"{'Strategy':<20} {'Symbol':<10} {'Signals':>8} {'TP%':>7} {'SL%':>7} {'TO%':>7}  Status",
        "-" * 72,
    ]

    strat_names = sorted({t.strategy for t in result.trades})
    any_zero = False

    for name in strat_names:
        for sym in sorted(result.config.symbols):
            st = [t for t in result.trades if t.strategy == name and t.symbol == sym]
            n  = len(st)
            if n == 0:
                status = "⚠  ZERO — check strategy config / data"
                any_zero = True
                lines.append(f"{name:<20} {sym:<10} {n:>8} {'—':>7} {'—':>7} {'—':>7}  {status}")
            else:
                tp_pct = sum(1 for t in st if t.exit_reason == "TP")     / n * 100
                sl_pct = sum(1 for t in st if t.exit_reason == "SL")     / n * 100
                to_pct = sum(1 for t in st if t.exit_reason == "TIMEOUT")/ n * 100
                status = "✅ OK"
                lines.append(
                    f"{name:<20} {sym:<10} {n:>8} {tp_pct:>6.1f}% {sl_pct:>6.1f}% {to_pct:>6.1f}%  {status}"
                )

    lines += [
        "-" * 72,
        "",
        "VERDICT: " + ("⚠  SOME STRATEGIES PRODUCED ZERO SIGNALS — do NOT proceed to demo"
                        if any_zero else
                        "✅ All strategies produced signals — proceed to gate check"),
        "",
        "Zero signals mean one of:",
        "  1. Data file missing or wrong filename (fetch_data.py)",
        "  2. Strategy adapter broken import",
        "  3. Date range outside available data",
        "  4. Session filter mismatch (check UTC hours in strategy)",
    ]

    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"[+] Smoke test  : {out}")
    return out
