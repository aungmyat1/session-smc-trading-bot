from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha1

import pandas as pd


@dataclass(frozen=True)
class NYMomentumConfig:
    enabled: bool = True
    london_session_start_hour: int = 8
    london_session_end_hour: int = 16
    ny_session_start_hour: int = 13
    ny_session_end_hour: int = 21
    sweep_buffer_pips: float = 1.0
    retest_tolerance_pips: float = 2.0
    stop_buffer_pips: float = 1.0
    rr_multiple: float = 2.0
    max_signals_per_day: int = 1
    strategy_name: str = "NYMomentum"


_PIP = {"EURUSD": 0.0001, "GBPUSD": 0.0001, "USDJPY": 0.01, "XAUUSD": 0.1}


def _pip_size(pair: str) -> float:
    return _PIP.get(pair.upper(), 0.0001)


def generate_ny_momentum_signals(
    candles: pd.DataFrame,
    pair: str | None = None,
    config: NYMomentumConfig | None = None,
) -> pd.DataFrame:
    """Generate NY sweep-and-retest signals off the London high/low."""
    cfg = config or NYMomentumConfig()
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
                "london_high",
                "london_low",
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
                "london_high",
                "london_low",
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
    for _, day in df.groupby("date", sort=True):
        london = day[
            (day["timestamp"].dt.hour >= cfg.london_session_start_hour)
            & (day["timestamp"].dt.hour < cfg.ny_session_start_hour)
        ].copy()
        ny = day[
            (day["timestamp"].dt.hour >= cfg.ny_session_start_hour)
            & (day["timestamp"].dt.hour < cfg.ny_session_end_hour)
        ].copy()
        if london.empty or ny.empty:
            continue

        london_high = float(london["high"].max())
        london_low = float(london["low"].min())
        if london_high <= london_low:
            continue

        swept_long = False
        swept_short = False
        awaiting_long = False
        awaiting_short = False
        _long_sweep_idx = None
        _short_sweep_idx = None

        for _, candle in ny.iterrows():
            ts = candle["timestamp"]
            close = float(candle["close"])
            high = float(candle["high"])
            low = float(candle["low"])

            if (
                not swept_long
                and high > london_high + cfg.sweep_buffer_pips * pip
                and close > london_high
            ):
                swept_long = True
                awaiting_long = True
                _long_sweep_idx = ts

            if (
                not swept_short
                and low < london_low - cfg.sweep_buffer_pips * pip
                and close < london_low
            ):
                swept_short = True
                awaiting_short = True
                _short_sweep_idx = ts

            if awaiting_long:
                retest_top = london_high + cfg.retest_tolerance_pips * pip
                retest_bot = london_high - cfg.retest_tolerance_pips * pip
                if retest_bot <= low <= retest_top or retest_bot <= close <= retest_top:
                    entry = close
                    stop_loss = london_low - cfg.stop_buffer_pips * pip
                    risk = entry - stop_loss
                    if risk > 0:
                        take_profit = entry + risk * cfg.rr_multiple
                        rows.append(
                            {
                                "signal_id": sha1(
                                    f"{cfg.strategy_name}-{pair}-{ts.isoformat()}-LONG".encode()
                                ).hexdigest()[:16],
                                "timestamp": ts,
                                "pair": pair,
                                "session": "new_york",
                                "direction": "LONG",
                                "strategy_name": cfg.strategy_name,
                                "entry_price": entry,
                                "stop_loss": round(stop_loss, 6),
                                "take_profit": round(take_profit, 6),
                                "london_high": london_high,
                                "london_low": london_low,
                                "confidence": 0.76,
                            }
                        )
                    awaiting_long = False
                    break

            if awaiting_short:
                retest_top = london_low + cfg.retest_tolerance_pips * pip
                retest_bot = london_low - cfg.retest_tolerance_pips * pip
                if (
                    retest_bot <= high <= retest_top
                    or retest_bot <= close <= retest_top
                ):
                    entry = close
                    stop_loss = london_high + cfg.stop_buffer_pips * pip
                    risk = stop_loss - entry
                    if risk > 0:
                        take_profit = entry - risk * cfg.rr_multiple
                        rows.append(
                            {
                                "signal_id": sha1(
                                    f"{cfg.strategy_name}-{pair}-{ts.isoformat()}-SHORT".encode()
                                ).hexdigest()[:16],
                                "timestamp": ts,
                                "pair": pair,
                                "session": "new_york",
                                "direction": "SHORT",
                                "strategy_name": cfg.strategy_name,
                                "entry_price": entry,
                                "stop_loss": round(stop_loss, 6),
                                "take_profit": round(take_profit, 6),
                                "london_high": london_high,
                                "london_low": london_low,
                                "confidence": 0.76,
                            }
                        )
                    awaiting_short = False
                    break

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
            "london_high",
            "london_low",
            "confidence",
        ],
    )
    if out.empty:
        return out

    out = out.sort_values(["pair", "timestamp"]).reset_index(drop=True)
    if cfg.max_signals_per_day > 0:
        out["date"] = out["timestamp"].dt.floor("D")
        out = out.groupby(["pair", "date"], group_keys=False).head(
            cfg.max_signals_per_day
        )
        out = out.drop(columns=["date"]).reset_index(drop=True)
    return out
