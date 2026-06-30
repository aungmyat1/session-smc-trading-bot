from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from execution_validation.replay_bridge import (
    build_validation_payload_from_candles,
    run_replay_validation_from_candles,
)

UTC = timezone.utc
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
        TRADE_DATE.year, TRADE_DATE.month, TRADE_DATE.day, tzinfo=UTC
    ) - timedelta(days=1)
    start = prev.replace(hour=23, minute=0)
    return [_bar(start + timedelta(minutes=15 * i), 1.0750, 1.0700) for i in range(32)]


def _h4_bullish() -> list[dict]:
    highs = [1, 2, 5, 2, 1, 2, 3, 3, 2, 1, 8, 2, 1]
    lows = [0.5, 1, 0.8, 0.5, 0.2, 0.8, 0.5, 0.8, 0.5, 0.3, 1.5, 0.5, 0.2]
    base = datetime(2024, 1, 12, 0, 0, tzinfo=UTC)
    return [
        _bar(base + timedelta(hours=4 * i), float(h), float(lo))
        for i, (h, lo) in enumerate(zip(highs, lows))
    ]


def _full_day() -> list[dict]:
    bars = _asian_bars()
    bars.append(
        _bar(datetime(2024, 1, 15, 7, 0, tzinfo=UTC), 1.0740, 1.0710, close=1.0730)
    )
    bars.append(
        _bar(
            datetime(2024, 1, 15, 7, 15, tzinfo=UTC),
            1.0748,
            1.0682,
            open_=1.0725,
            close=1.0720,
        )
    )
    bars.append(
        _bar(
            datetime(2024, 1, 15, 7, 30, tzinfo=UTC),
            1.0800,
            1.0695,
            open_=1.0700,
            close=1.0790,
        )
    )
    return bars


@pytest.mark.asyncio
async def test_build_validation_payload_from_candles_produces_suite_artifacts():
    payload = await build_validation_payload_from_candles(
        strategy="ST-A2",
        period="2024-01-15",
        symbol="EURUSD",
        candles_m15=_full_day(),
        candles_h4=_h4_bullish(),
        spread_pips=1.0,
        backtest_pf=1.5,
        virtual_pf=1.45,
    )

    assert payload.signals
    assert payload.orders
    assert payload.fills
    assert payload.execution_events
    assert payload.broker_rule_samples
    assert payload.recovery_snapshot["connected"] is True


@pytest.mark.asyncio
async def test_run_replay_validation_from_candles_writes_report(tmp_path):
    report = await run_replay_validation_from_candles(
        strategy="ST-A2",
        period="2024-01-15",
        symbol="EURUSD",
        candles_m15=_full_day(),
        candles_h4=_h4_bullish(),
        report_dir=tmp_path,
        spread_pips=1.0,
        backtest_pf=1.5,
        virtual_pf=1.45,
    )

    assert report.status == "READY FOR DEMO"
    assert (tmp_path / "validation_report.json").exists()
