from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha1

import pandas as pd


@dataclass(frozen=True)
class LondonBreakoutConfig:
    enabled: bool = True
    asian_session_end_hour: int = 8
    london_session_start_hour: int = 8
    london_session_end_hour: int = 16
    min_asian_range_pips: float = 15.0
    max_asian_range_pips: float = 50.0
    retest_tolerance_pips: float = 0.5
    stop_buffer_pips: float = 1.0
    rr_multiple: float = 1.5
    max_signals_per_day: int = 1
    strategy_name: str = "LondonBreakout"


_PIP = {"EURUSD": 0.0001, "GBPUSD": 0.0001, "XAUUSD": 0.1, "USDJPY": 0.01}


def _pip_size(pair: str) -> float:
    return _PIP.get(pair.upper(), 0.0001)


def generate_london_breakout_signals(
    candles: pd.DataFrame,
    pair: str | None = None,
    config: LondonBreakoutConfig | None = None,
) -> pd.DataFrame:
    """Generate one London breakout signal per day when the Asian range is broken and retested."""
    cfg = config or LondonBreakoutConfig()
    if not cfg.enabled:
        return pd.DataFrame(
            columns=[
                "signal_id",
                "timestamp",
                "pair",
                "session",
                "direction",
                "strategy_name",
                "entry_price",
                "stop_loss",
                "take_profit",
                "asian_high",
                "asian_low",
                "range_pips",
                "breakout_time",
                "breakout_price",
                "retest_time",
                "confidence",
            ]
        )
    df = candles.copy()
    if df.empty:
        return pd.DataFrame(
            columns=[
                "signal_id",
                "timestamp",
                "pair",
                "session",
                "direction",
                "strategy_name",
                "entry_price",
                "stop_loss",
                "take_profit",
                "asian_high",
                "asian_low",
                "range_pips",
                "breakout_time",
                "breakout_price",
                "retest_time",
                "confidence",
            ]
        )

    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    if pair is None and "pair" in df.columns and not df["pair"].empty:
        pair = str(df["pair"].iloc[0])
    pair = pair or ""
    pip = _pip_size(pair)

    rows: list[dict] = []
    df["date"] = df["timestamp"].dt.floor("D")
    for date, day in df.groupby("date", sort=True):
        asian = day[day["timestamp"].dt.hour < cfg.asian_session_end_hour]
        london = day[
            (day["timestamp"].dt.hour >= cfg.london_session_start_hour)
            & (day["timestamp"].dt.hour < cfg.london_session_end_hour)
        ]
        if asian.empty or london.empty:
            continue

        asian_high = float(asian["high"].max())
        asian_low = float(asian["low"].min())
        range_pips = (asian_high - asian_low) / pip
        if range_pips < cfg.min_asian_range_pips or range_pips > cfg.max_asian_range_pips:
            continue

        breakout_direction: str | None = None
        breakout_time = None
        breakout_price = None
        day_rows: list[dict] = []

        for _, candle in london.iterrows():
            ts = candle["timestamp"]
            close = float(candle["close"])
            high = float(candle["high"])
            low = float(candle["low"])
            if breakout_direction is None:
                if close > asian_high:
                    breakout_direction = "LONG"
                    breakout_time = ts
                    breakout_price = close
                    continue
                if close < asian_low:
                    breakout_direction = "SHORT"
                    breakout_time = ts
                    breakout_price = close
                    continue

            if breakout_direction == "LONG":
                retest_low = asian_high - cfg.retest_tolerance_pips * pip
                retest_high = asian_high + 2.0 * pip
                if low <= retest_high and low >= retest_low and close >= asian_high:
                    entry = close
                    stop_loss = asian_low - cfg.stop_buffer_pips * pip
                    risk = entry - stop_loss
                    if risk <= 0:
                        breakout_direction = None
                        continue
                    take_profit = entry + risk * cfg.rr_multiple
                    day_rows.append(
                        {
                            "signal_id": sha1(
                                f"{cfg.strategy_name}-{pair}-{ts.isoformat()}-LONG".encode()
                            ).hexdigest()[:16],
                            "timestamp": ts,
                            "pair": pair,
                            "session": "london",
                            "direction": "LONG",
                            "strategy_name": cfg.strategy_name,
                            "entry_price": entry,
                            "stop_loss": stop_loss,
                            "take_profit": take_profit,
                            "asian_high": asian_high,
                            "asian_low": asian_low,
                            "range_pips": range_pips,
                            "breakout_time": breakout_time,
                            "breakout_price": breakout_price,
                            "retest_time": ts,
                            "confidence": round(min(0.95, 0.6 + min(0.3, range_pips / 100.0)), 2),
                        }
                    )
                    breakout_direction = None
                    break

            elif breakout_direction == "SHORT":
                retest_low = asian_low - 2.0 * pip
                retest_high = asian_low + cfg.retest_tolerance_pips * pip
                if low <= retest_high and high >= retest_low and close <= asian_low:
                    entry = close
                    stop_loss = asian_high + cfg.stop_buffer_pips * pip
                    risk = stop_loss - entry
                    if risk <= 0:
                        breakout_direction = None
                        continue
                    take_profit = entry - risk * cfg.rr_multiple
                    day_rows.append(
                        {
                            "signal_id": sha1(
                                f"{cfg.strategy_name}-{pair}-{ts.isoformat()}-SHORT".encode()
                            ).hexdigest()[:16],
                            "timestamp": ts,
                            "pair": pair,
                            "session": "london",
                            "direction": "SHORT",
                            "strategy_name": cfg.strategy_name,
                            "entry_price": entry,
                            "stop_loss": stop_loss,
                            "take_profit": take_profit,
                            "asian_high": asian_high,
                            "asian_low": asian_low,
                            "range_pips": range_pips,
                            "breakout_time": breakout_time,
                            "breakout_price": breakout_price,
                            "retest_time": ts,
                            "confidence": round(min(0.95, 0.6 + min(0.3, range_pips / 100.0)), 2),
                        }
                    )
                    breakout_direction = None
                    break

        rows.extend(day_rows[: cfg.max_signals_per_day] if cfg.max_signals_per_day > 0 else day_rows)

    out = pd.DataFrame.from_records(
        rows,
        columns=[
            "signal_id",
            "timestamp",
            "pair",
            "session",
            "direction",
            "strategy_name",
            "entry_price",
            "stop_loss",
            "take_profit",
            "asian_high",
            "asian_low",
            "range_pips",
            "breakout_time",
            "breakout_price",
            "retest_time",
            "confidence",
        ],
    )
    if out.empty:
        return out
    out = out.sort_values(["pair", "timestamp"]).reset_index(drop=True)
    if cfg.max_signals_per_day > 0:
        out["date"] = out["timestamp"].dt.floor("D")
        out = out.groupby(["pair", "date"], group_keys=False).head(cfg.max_signals_per_day)
        out = out.drop(columns=["date"]).reset_index(drop=True)
    return out
