"""
Historical replay audit.

This sits beside the forward-test simulator, but its job is different:
it treats replay as a deterministic execution audit, not a profitability test.

What it answers:
    - Did the strategy produce the same signals as the batch backtest?
    - Did the strategy emit the signal on the first candle it could know?
    - Did the debug timeline show the expected sweep → displacement → signal flow?

What it does NOT answer:
    - Whether the strategy is profitable. Use backtest scripts for that.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date as date_cls, datetime, timezone
from typing import Iterable

from simulator.forward_test import (
    ForwardTestSimulator,
    ReplayEvent,
    compare_with_backtest,
    format_replay,
    replay_day,
)
from strategy.session_liquidity.entry_engine import Signal
from strategy.session_liquidity.session_strategy import DEFAULT_CONFIG

_UTC = timezone.utc


@dataclass
class HistoricalReplayDay:
    trade_date: date_cls
    timeline: list[ReplayEvent]
    signals: list[Signal]
    match_with_backtest: bool
    mismatches: list[str]

    @property
    def signal_count(self) -> int:
        return len(self.signals)


@dataclass
class HistoricalReplayReport:
    symbol: str
    start: str | None
    end: str | None
    days: list[HistoricalReplayDay]
    backtest_match: bool
    backtest_mismatches: list[str]
    total_signals: int
    signal_days: int
    total_days: int

    @property
    def no_trade_days(self) -> int:
        return self.total_days - self.signal_days


def _parse_date(value: str | date_cls | None) -> date_cls | None:
    if value is None:
        return None
    if isinstance(value, date_cls):
        return value
    if "T" in value:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    return datetime.strptime(value, "%Y-%m-%d").date()


def _bar_date(bar: dict) -> date_cls:
    raw = bar["time"]
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=_UTC)
    return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))


def _day_key(bar: dict) -> date_cls:
    return _bar_date(bar).date()


def _filter_by_date(
    bars: Iterable[dict],
    start: date_cls | None,
    end: date_cls | None,
) -> list[dict]:
    out = []
    for bar in bars:
        d = _day_key(bar)
        if start and d < start:
            continue
        if end and d > end:
            continue
        out.append(bar)
    return out


def run_historical_replay(
    symbol: str,
    candles_m15: list[dict],
    candles_4h: list[dict],
    config: dict | None = None,
    start: str | date_cls | None = None,
    end: str | date_cls | None = None,
    signal_days_only: bool = True,
) -> HistoricalReplayReport:
    """
    Replay a historical window and package it as an execution audit.

    The full-window backtest comparison is performed once, while the day-by-day
    replay timeline is produced from the sequential feed path.
    """
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    start_date = _parse_date(start)
    end_date = _parse_date(end)

    m15 = sorted(_filter_by_date(candles_m15, start_date, end_date), key=lambda b: b["time"])
    h4 = sorted(candles_4h, key=lambda b: b["time"])

    # Sequential feed gives us the true replay signal path.
    simulator = ForwardTestSimulator(symbol, config=cfg, h4_candles=h4)
    signals_by_day: dict[date_cls, list[Signal]] = defaultdict(list)
    history: list[dict] = []
    bars_by_day: dict[date_cls, list[dict]] = defaultdict(list)
    for bar in m15:
        bars_by_day[_day_key(bar)].append(bar)

    for d in sorted(bars_by_day):
        day_bars = bars_by_day[d]
        history.extend(day_bars)
        new_signals = simulator.feed_all(day_bars)
        if new_signals:
            signals_by_day[d].extend(new_signals)

    comparison = compare_with_backtest(symbol, m15, h4, config=cfg)

    days: list[HistoricalReplayDay] = []
    cumulative_history: list[dict] = []
    for d in sorted(bars_by_day):
        day_bars = bars_by_day[d]
        cumulative_history.extend(day_bars)
        day_signals = signals_by_day.get(d, [])
        if signal_days_only and not day_signals:
            continue

        timeline = replay_day(d, symbol, list(cumulative_history), h4, config=cfg)
        day_mismatches: list[str] = []
        day_match = True
        if day_signals:
            # Compare against the batch signal list for this day only.
            # This keeps the audit focused on "did the bot do the right thing?".
            day_debug_signals = [
                ev for ev in timeline if ev.event == "SIGNAL"
            ]
            if len(day_debug_signals) != len(day_signals):
                day_match = False
                day_mismatches.append(
                    f"signal_count debug={len(day_debug_signals)} seq={len(day_signals)}"
                )

        days.append(
            HistoricalReplayDay(
                trade_date=d,
                timeline=timeline,
                signals=day_signals,
                match_with_backtest=day_match,
                mismatches=day_mismatches,
            )
        )

    total_signals = sum(len(v) for v in signals_by_day.values())
    signal_days = sum(1 for v in signals_by_day.values() if v)

    return HistoricalReplayReport(
        symbol=symbol,
        start=str(start_date) if start_date else None,
        end=str(end_date) if end_date else None,
        days=days,
        backtest_match=bool(comparison["match"]),
        backtest_mismatches=list(comparison["mismatches"]),
        total_signals=total_signals,
        signal_days=signal_days,
        total_days=len(bars_by_day),
    )


def render_report(report: HistoricalReplayReport) -> str:
    """Render a markdown audit report."""
    lines: list[str] = [
        "# Historical Replay Audit",
        "",
        f"Symbol: `{report.symbol}`",
        f"Window: `{report.start or 'full history'}` → `{report.end or 'full history'}`",
        "",
        "## Purpose",
        "",
        "Historical replay validates execution logic and signal timing. It does not measure profitability; use the backtest for that.",
        "",
        "## Summary",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Total days | {report.total_days} |",
        f"| Signal days | {report.signal_days} |",
        f"| No-trade days | {report.no_trade_days} |",
        f"| Total signals | {report.total_signals} |",
        f"| Backtest match | {'PASS' if report.backtest_match else 'FAIL'} |",
    ]

    if report.backtest_mismatches:
        lines += ["", "## Backtest Mismatches", ""]
        for mismatch in report.backtest_mismatches:
            lines.append(f"- {mismatch}")

    for day in report.days:
        lines += [
            "",
            f"## {day.trade_date}",
            "",
            f"- Signals: {day.signal_count}",
            f"- Replay/backtest consistency: {'PASS' if day.match_with_backtest else 'FAIL'}",
        ]
        if day.mismatches:
            lines.append(f"- Mismatches: {', '.join(day.mismatches)}")
        lines += [
            "",
            "```text",
            format_replay(day.timeline, title=f"{day.trade_date} {report.symbol}"),
            "```",
        ]

    return "\n".join(lines)


def report_to_dict(report: HistoricalReplayReport) -> dict:
    return {
        "symbol": report.symbol,
        "start": report.start,
        "end": report.end,
        "backtest_match": report.backtest_match,
        "backtest_mismatches": list(report.backtest_mismatches),
        "total_signals": report.total_signals,
        "signal_days": report.signal_days,
        "total_days": report.total_days,
        "days": [
            {
                "trade_date": str(day.trade_date),
                "signal_count": day.signal_count,
                "match_with_backtest": day.match_with_backtest,
                "mismatches": list(day.mismatches),
                "timeline": [
                    {"time": ev.time, "event": ev.event, "detail": ev.detail}
                    for ev in day.timeline
                ],
            }
            for day in report.days
        ],
    }
