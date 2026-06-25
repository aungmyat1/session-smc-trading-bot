"""
execution_rules.py
Defines entry, stop loss, and take profit logic.
"""

from typing import Dict, Optional
import polars as pl


def get_entry_price(signal: Dict, candles: pl.DataFrame) -> Optional[float]:
    """
    Simplified entry rule (v1):
    - Use next candle's open after signal time
    """
    signal_time = signal["time"]
    next_candle = candles.filter(pl.col("time") > signal_time).head(1)

    if next_candle.is_empty():
        return None

    return float(next_candle["open"][0])


def get_stop_loss(signal: Dict, candles: pl.DataFrame) -> Optional[float]:
    """
    Stop Loss rules:
    - LONG: below the sweep low (if available)
    - SHORT: above the sweep high
    """
    direction = signal.get("direction")
    sweep = signal.get("sweep")

    # Fallback: use recent swing low/high from swings data if available
    if direction == "LONG":
        if sweep == "sweep_low":
            # Use the low of the candle that created the sweep
            return float(candles.filter(pl.col("time") == signal["time"])["low"][0])
        else:
            # Use previous swing low
            return float(candles["low"].min())
    else:  # SHORT
        if sweep == "sweep_high":
            return float(candles.filter(pl.col("time") == signal["time"])["high"][0])
        else:
            return float(candles["high"].max())

    return None


def get_take_profit(entry: float, stop: float, direction: str, rr: float = 2.0) -> float:
    """
    Fixed Risk-Reward Take Profit
    """
    risk = abs(entry - stop)
    if direction == "LONG":
        return entry + risk * rr
    else:
        return entry - risk * rr