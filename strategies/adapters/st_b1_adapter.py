"""Runtime adapter for ST-B1 Simple Trend Pullback."""

from __future__ import annotations

from core.base_strategy import BaseStrategy
from shared.strategy_api import Signal
from strategies.st_b1_backtest import normalize_bars, session_for_timestamp
from strategies.st_b1_simple_pullback import compute_trend, detect_pullback, generate_orders


class STB1Adapter(BaseStrategy):
    @property
    def name(self) -> str:
        return "ST-B1"

    def generate_signal(self, data: dict) -> Signal | None:
        symbol = str(data.get("symbol", "")).upper()
        h1 = normalize_bars(data.get("h1", []))
        m15 = normalize_bars(data.get("m15", []))
        if len(h1) < 200 or len(m15) < 21:
            return None
        trend = compute_trend(h1, symbol=symbol)
        setup = detect_pullback(m15[:-1], trend)
        if setup is None:
            return None
        next_candle = dict(m15[-1])
        next_candle["session"] = next_candle.get("session") or session_for_timestamp(next_candle["timestamp"])
        return generate_orders(
            symbol=symbol,
            trend=trend,
            setup=setup,
            next_candle=next_candle,
            equity=float(data.get("equity", 10_000.0)),
            risk_pct=float(data.get("risk_pct", 0.25)),
            entry_tf_candles=h1,
            open_position_count=int(data.get("open_position_count", 0)),
        )
