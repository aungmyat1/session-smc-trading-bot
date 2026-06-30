"""
SMC Order Block + FVG Session adapter.

This adapter implements an intraday SMC setup around:
  - kill-zone session filtering
  - recent BOS detection
  - order block identification
  - fair value gap confirmation
  - ATR-based displacement and stop buffering

Input schema:
    {
        "symbol": str,
        "m15": list[dict],         # required; accepts "time" or "timestamp"
        "spread_pips": float,      # optional
        "config": dict,            # optional overrides
    }
"""

from __future__ import annotations

from datetime import datetime, time, timezone
from typing import Optional

import pandas as pd

from core.base_strategy import BaseStrategy
from core.signal import Signal
from src.features.fvg import detect_fvg
from src.features.order_blocks import detect_order_blocks

_PIP = {
    "EURUSD": 0.0001,
    "GBPUSD": 0.0001,
    "USDJPY": 0.01,
    "XAUUSD": 0.1,
}

DEFAULT_CONFIG = {
    "risk_per_trade": 0.01,
    "rr_ratio": 3.0,
    "atr_period": 14,
    "ob_lookback": 50,
    "bos_lookback": 20,
    "signal_lookback_bars": 12,
    "fvg_threshold": 0.0,
    "min_atr_displacement": 1.0,
    "stop_buffer_pips": 5.0,
    "max_spread_pips": 3.0,
    "london_start": "07:00",
    "london_end": "11:00",
    "ny_start": "12:00",
    "ny_end": "16:00",
    "max_daily_trades": 2,
    "use_equity_bagging": True,
}


def _parse_hhmm(value: str) -> time:
    hour, minute = str(value).split(":", 1)
    return time(int(hour), int(minute))


def _normalize_frame(candles: list[dict]) -> pd.DataFrame:
    rows: list[dict] = []
    for candle in candles:
        ts = candle.get("timestamp", candle.get("time"))
        if ts is None:
            continue
        rows.append(
            {
                "timestamp": ts,
                "open": float(candle["open"]),
                "high": float(candle["high"]),
                "low": float(candle["low"]),
                "close": float(candle["close"]),
                "volume": float(candle.get("volume", candle.get("tickVolume", 0))),
            }
        )
    frame = pd.DataFrame.from_records(rows)
    if frame.empty:
        return frame
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    return frame.sort_values("timestamp").reset_index(drop=True)


def _atr(frame: pd.DataFrame, period: int) -> pd.Series:
    prev_close = frame["close"].shift(1)
    tr = pd.concat(
        [
            frame["high"] - frame["low"],
            (frame["high"] - prev_close).abs(),
            (frame["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.rolling(period, min_periods=period).mean()


def _in_window(ts: pd.Timestamp, start_text: str, end_text: str) -> bool:
    current = ts.time()
    start = _parse_hhmm(start_text)
    end = _parse_hhmm(end_text)
    return start <= current < end


def _current_session(ts: pd.Timestamp, config: dict) -> Optional[str]:
    if _in_window(ts, config["london_start"], config["london_end"]):
        return "london"
    if _in_window(ts, config["ny_start"], config["ny_end"]):
        return "new_york"
    return None


def _latest_bos(frame: pd.DataFrame, config: dict, pair: str) -> Optional[dict]:
    lookback = max(int(config["bos_lookback"]), 2)
    scan_start = max(
        lookback, len(frame) - max(int(config["ob_lookback"]), lookback) - 1
    )
    records: list[dict] = []

    for idx in range(scan_start, len(frame) - 1):
        prior = frame.iloc[idx - lookback : idx]
        if prior.empty:
            continue
        candle = frame.iloc[idx]
        direction = None
        if candle["close"] > float(prior["high"].max()):
            direction = "bullish"
        elif candle["close"] < float(prior["low"].min()):
            direction = "bearish"
        if direction is None:
            continue
        records.append(
            {
                "timestamp": candle["timestamp"],
                "pair": pair,
                "structure": "BOS",
                "direction": direction,
                "index": idx,
            }
        )

    if not records:
        return None
    return records[-1]


def _gap_size(row: pd.Series) -> float:
    return abs(float(row["high"]) - float(row["low"]))


def _zone_distance(low_a: float, high_a: float, low_b: float, high_b: float) -> float:
    if high_a < low_b:
        return low_b - high_a
    if high_b < low_a:
        return low_a - high_b
    return 0.0


class SMCOrderBlockFVGSessionAdapter(BaseStrategy):
    @property
    def name(self) -> str:
        return "SMCOrderBlockFVGSession"

    def generate_signal(self, data: dict) -> Optional[Signal]:
        symbol = str(data.get("symbol", "")).strip()
        candles = data.get("m15", [])
        config = {**DEFAULT_CONFIG, **(data.get("config") or {})}

        if not symbol or len(candles) < max(
            int(config["ob_lookback"]), int(config["atr_period"]) + 5
        ):
            return None

        spread_pips = float(data.get("spread_pips", 0.0) or 0.0)
        if spread_pips and spread_pips > float(config["max_spread_pips"]):
            return None

        frame = _normalize_frame(candles)
        if frame.empty:
            return None

        latest = frame.iloc[-1]
        session = _current_session(latest["timestamp"], config)
        if session is None:
            return None

        frame["atr"] = _atr(frame, int(config["atr_period"]))
        latest_atr = (
            float(frame["atr"].iloc[-1]) if pd.notna(frame["atr"].iloc[-1]) else 0.0
        )
        if latest_atr <= 0:
            return None

        bos = _latest_bos(frame, config, symbol)
        if bos is None:
            return None

        structure = pd.DataFrame.from_records(
            [bos], columns=["timestamp", "pair", "structure", "direction", "index"]
        )
        order_blocks = detect_order_blocks(
            frame,
            structure[["timestamp", "pair", "structure", "direction"]],
            pair=symbol,
        )
        if order_blocks.empty:
            return None

        ob = order_blocks.iloc[-1]
        fvgs = detect_fvg(frame, pair=symbol)
        if fvgs.empty:
            return None
        fvgs = fvgs[
            (fvgs["direction"] == bos["direction"])
            & (fvgs["timestamp"] >= ob["time"])
            & (fvgs["timestamp"] <= latest["timestamp"])
        ].copy()
        if fvgs.empty:
            return None
        fvgs = fvgs[fvgs.apply(_gap_size, axis=1) >= float(config["fvg_threshold"])]
        if fvgs.empty:
            return None

        fvg = fvgs.iloc[-1]
        ob_low = float(ob["low"])
        ob_high = float(ob["high"])
        fvg_low = float(fvg["low"])
        fvg_high = float(fvg["high"])
        zone_distance = _zone_distance(ob_low, ob_high, fvg_low, fvg_high)
        if zone_distance > latest_atr * 0.5:
            return None

        bos_index = int(bos["index"])
        bos_candle = frame.iloc[bos_index]
        bos_body = abs(float(bos_candle["close"]) - float(bos_candle["open"]))
        if bos_body < latest_atr * float(config["min_atr_displacement"]):
            return None

        entry = float(latest["close"])
        pip = _PIP.get(symbol, 0.0001)
        buffer_size = float(config["stop_buffer_pips"]) * pip
        rr = float(config["rr_ratio"])

        if bos["direction"] == "bullish":
            zone_top = max(ob_high, fvg_high)
            zone_floor = min(ob_low, fvg_low)
            if not (zone_floor <= entry <= zone_top):
                return None
            stop_loss = zone_floor - buffer_size
            risk = entry - stop_loss
            if risk <= 0:
                return None
            take_profit = entry + (risk * rr)
            action = "BUY"
        else:
            zone_top = max(ob_high, fvg_high)
            zone_floor = min(ob_low, fvg_low)
            if not (zone_floor <= entry <= zone_top):
                return None
            stop_loss = zone_top + buffer_size
            risk = stop_loss - entry
            if risk <= 0:
                return None
            take_profit = entry - (risk * rr)
            action = "SELL"

        asian_mask = (
            (frame["timestamp"].dt.date == latest["timestamp"].date())
            & (frame["timestamp"].dt.hour >= 0)
            & (frame["timestamp"].dt.hour < 8)
        )
        asian = frame.loc[asian_mask]

        return Signal(
            timestamp=datetime.now(timezone.utc).isoformat(),
            strategy_name=self.name,
            symbol=symbol,
            action=action,
            order_type="MARKET",
            entry_price=entry,
            stop_loss=float(stop_loss),
            take_profit=float(take_profit),
            risk_percent=float(config["risk_per_trade"]) * 100.0,
            confidence=min(1.0, rr / 3.0),
            metadata={
                "session": session,
                "reason": "order_block_fvg_bos_confluence",
                "structure": bos["structure"],
                "structure_direction": bos["direction"],
                "risk_pips": round(risk / pip, 2),
                "reward_pips": round(abs(take_profit - entry) / pip, 2),
                "rr": rr,
                "order_block_low": ob_low,
                "order_block_high": ob_high,
                "fvg_low": fvg_low,
                "fvg_high": fvg_high,
                "asian_high": float(asian["high"].max()) if not asian.empty else None,
                "asian_low": float(asian["low"].min()) if not asian.empty else None,
                "spread_pips": spread_pips,
                "use_equity_bagging": bool(config["use_equity_bagging"]),
                "max_daily_trades": int(config["max_daily_trades"]),
            },
        )
