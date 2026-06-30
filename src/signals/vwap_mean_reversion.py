from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha1

import pandas as pd


@dataclass(frozen=True)
class VWAPMeanReversionConfig:
    enabled: bool = True
    london_session_start_hour: int = 8
    london_session_end_hour: int = 16
    new_york_session_start_hour: int = 13
    new_york_session_end_hour: int = 21
    min_session_bars: int = 8
    min_bars: int = 12
    sweep_buffer_mult: float = 0.35
    extreme_atr_mult: float = 1.0
    reclaim_atr_mult: float = 0.6
    tp_rr: float = 1.8
    max_signals_per_day: int = 1
    strategy_name: str = "VWAPMeanReversion"


_PIP = {"EURUSD": 0.0001, "GBPUSD": 0.0001, "USDJPY": 0.01, "XAUUSD": 0.1}


def _pip_size(pair: str) -> float:
    return _PIP.get(pair.upper(), 0.0001)


def _session_name(hour: int, cfg: VWAPMeanReversionConfig) -> str:
    if cfg.london_session_start_hour <= hour < cfg.london_session_end_hour:
        return "london"
    if cfg.new_york_session_start_hour <= hour < cfg.new_york_session_end_hour:
        return "new_york"
    return ""


def _calc_vwap(candles: pd.DataFrame) -> float:
    typical = (candles["high"] + candles["low"] + candles["close"]) / 3.0
    volume = candles["volume"].replace(0, 1)
    total_v = float(volume.sum())
    return float((typical * volume).sum() / total_v) if total_v else 0.0


def _calc_atr(candles: pd.DataFrame) -> float:
    if len(candles) < 2:
        return 0.0
    prev_close = candles["close"].shift(1)
    tr = pd.concat(
        [
            candles["high"] - candles["low"],
            (candles["high"] - prev_close).abs(),
            (candles["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return float(tr.iloc[1:].mean())


def generate_vwap_mean_reversion_signals(
    candles: pd.DataFrame,
    pair: str | None = None,
    config: VWAPMeanReversionConfig | None = None,
) -> pd.DataFrame:
    """Generate session-scoped VWAP mean-reversion signals."""
    cfg = config or VWAPMeanReversionConfig()
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
                "vwap",
                "atr",
                "distance_from_vwap",
                "distance_atr",
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
                "vwap",
                "atr",
                "distance_from_vwap",
                "distance_atr",
                "confidence",
            ]
        )

    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    if pair is None and "pair" in df.columns and not df["pair"].empty:
        pair = str(df["pair"].iloc[0])
    pair = pair or ""
    pip = _pip_size(pair)

    if "volume" not in df.columns:
        df["volume"] = 1.0

    rows: list[dict] = []
    df["date"] = df["timestamp"].dt.floor("D")
    for _, day in df.groupby("date", sort=True):
        for session in ("london", "new_york"):
            sess = day[
                day["timestamp"].dt.hour.map(lambda hour: _session_name(hour, cfg))
                == session
            ].copy()
            if len(sess) < max(cfg.min_bars, cfg.min_session_bars):
                continue

            sess = sess.sort_values("timestamp").reset_index(drop=True)
            vwap = _calc_vwap(sess)
            atr = _calc_atr(sess)
            if vwap <= 0 or atr <= 0:
                continue

            last = sess.iloc[-1]
            prev = sess.iloc[-2]
            close = float(last["close"])
            high = float(last["high"])
            low = float(last["low"])
            prev_close = float(prev["close"])

            lookback = min(5, len(sess) - 1)
            prior_window = sess.iloc[-(lookback + 1) : -1]
            rolling_high = float(prior_window["high"].max())
            rolling_low = float(prior_window["low"].min())
            sweep_buffer = max(pip * cfg.sweep_buffer_mult, atr * 0.1)

            distance_from_vwap = abs(close - vwap)
            distance_atr = distance_from_vwap / atr

            long_sweep = low < rolling_low - sweep_buffer
            long_reclaim = (
                close > prev_close and (close - low) >= atr * cfg.reclaim_atr_mult
            )
            long_extension = vwap - close >= atr * cfg.extreme_atr_mult
            if long_sweep and long_reclaim and long_extension and close < vwap:
                entry = close
                stop_loss = low - 1.5 * pip
                risk = entry - stop_loss
                if risk > 0:
                    take_profit = min(vwap, entry + risk * cfg.tp_rr)
                    reward = take_profit - entry
                    if reward > 0:
                        rows.append(
                            {
                                "signal_id": sha1(
                                    f"{cfg.strategy_name}-{pair}-{last['timestamp'].isoformat()}-LONG".encode()
                                ).hexdigest()[:16],
                                "timestamp": last["timestamp"],
                                "pair": pair,
                                "session": session,
                                "direction": "LONG",
                                "strategy_name": cfg.strategy_name,
                                "entry_price": entry,
                                "stop_loss": round(stop_loss, 6),
                                "take_profit": round(take_profit, 6),
                                "vwap": round(vwap, 6),
                                "atr": round(atr, 6),
                                "distance_from_vwap": round(distance_from_vwap, 6),
                                "distance_atr": round(distance_atr, 2),
                                "confidence": round(
                                    min(0.95, 0.62 + min(0.28, distance_atr / 6.0)), 2
                                ),
                            }
                        )

            short_sweep = high > rolling_high + sweep_buffer
            short_reclaim = (
                close < prev_close and (high - close) >= atr * cfg.reclaim_atr_mult
            )
            short_extension = close - vwap >= atr * cfg.extreme_atr_mult
            if short_sweep and short_reclaim and short_extension and close > vwap:
                entry = close
                stop_loss = high + 1.5 * pip
                risk = stop_loss - entry
                if risk > 0:
                    take_profit = max(vwap, entry - risk * cfg.tp_rr)
                    reward = entry - take_profit
                    if reward > 0:
                        rows.append(
                            {
                                "signal_id": sha1(
                                    f"{cfg.strategy_name}-{pair}-{last['timestamp'].isoformat()}-SHORT".encode()
                                ).hexdigest()[:16],
                                "timestamp": last["timestamp"],
                                "pair": pair,
                                "session": session,
                                "direction": "SHORT",
                                "strategy_name": cfg.strategy_name,
                                "entry_price": entry,
                                "stop_loss": round(stop_loss, 6),
                                "take_profit": round(take_profit, 6),
                                "vwap": round(vwap, 6),
                                "atr": round(atr, 6),
                                "distance_from_vwap": round(distance_from_vwap, 6),
                                "distance_atr": round(distance_atr, 2),
                                "confidence": round(
                                    min(0.95, 0.62 + min(0.28, distance_atr / 6.0)), 2
                                ),
                            }
                        )

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
            "vwap",
            "atr",
            "distance_from_vwap",
            "distance_atr",
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
