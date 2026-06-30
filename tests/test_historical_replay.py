"""Tests for the historical replay audit runner."""

from datetime import date, datetime, timedelta, timezone

from simulator.historical_replay import (
    render_report,
    report_to_dict,
    run_historical_replay,
)

_UTC = timezone.utc
TRADE_DATE = date(2024, 1, 15)


def _bar(
    t: datetime,
    high: float,
    low: float,
    open_: float | None = None,
    close: float | None = None,
) -> dict:
    mid = round((high + low) / 2, 6)
    return {
        "time": t.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "open": open_ if open_ is not None else mid,
        "high": high,
        "low": low,
        "close": close if close is not None else mid,
        "volume": 100.0,
    }


def _asian_bars() -> list[dict]:
    prev = datetime(
        TRADE_DATE.year, TRADE_DATE.month, TRADE_DATE.day, tzinfo=_UTC
    ) - timedelta(days=1)
    start = prev.replace(hour=23, minute=0)
    return [_bar(start + timedelta(minutes=15 * i), 1.0750, 1.0700) for i in range(32)]


def _h4_bullish() -> list[dict]:
    highs = [1, 2, 5, 2, 1, 2, 3, 3, 2, 1, 8, 2, 1]
    lows = [0.5, 1, 0.8, 0.5, 0.2, 0.8, 0.5, 0.8, 0.5, 0.3, 1.5, 0.5, 0.2]
    base = datetime(2024, 1, 12, 0, 0, tzinfo=_UTC)
    return [
        _bar(base + timedelta(hours=4 * i), float(h), float(lo))
        for i, (h, lo) in enumerate(zip(highs, lows))
    ]


def _full_day() -> list[dict]:
    bars = _asian_bars()
    bars.append(
        _bar(datetime(2024, 1, 15, 7, 0, tzinfo=_UTC), 1.0740, 1.0710, close=1.0730)
    )
    bars.append(
        _bar(
            datetime(2024, 1, 15, 7, 15, tzinfo=_UTC),
            1.0748,
            1.0682,
            open_=1.0725,
            close=1.0720,
        )
    )
    bars.append(
        _bar(
            datetime(2024, 1, 15, 7, 30, tzinfo=_UTC),
            1.0800,
            1.0695,
            open_=1.0700,
            close=1.0790,
        )
    )
    return bars


def test_historical_replay_matches_backtest_on_fixture():
    report = run_historical_replay("EURUSD", _full_day(), _h4_bullish())

    assert report.backtest_match is True
    assert report.total_signals == 1
    assert report.signal_days == 1
    assert len(report.days) == 1
    assert any(ev.event == "SIGNAL" for ev in report.days[0].timeline)
    assert any(ev.event == "SWEEP" for ev in report.days[0].timeline)


def test_historical_replay_rendering_mentions_execution_not_profit():
    report = run_historical_replay("EURUSD", _full_day(), _h4_bullish())
    text = render_report(report)
    data = report_to_dict(report)

    assert "Historical replay validates execution logic" in text
    assert "Backtest match" in text
    assert data["symbol"] == "EURUSD"
    assert data["days"][0]["signal_count"] == 1
