"""
trade_engine.py
Core logic that converts a signal into a simulated trade.
"""

from typing import Dict, Optional
import polars as pl
from .execution_rules import get_entry_price, get_stop_loss, get_take_profit
from .risk_model import evaluate_r_multiple


def simulate_trade(
    signal: Dict,
    candles: pl.DataFrame,
    rr_multiple: float = 2.0
) -> Optional[Dict]:
    """
    Simulate one trade from a signal.

    Args:
        signal: dict from signals.parquet
        candles: full M1 dataframe for the pair
        rr_multiple: risk-reward ratio (default 2R)
    """
    entry = get_entry_price(signal, candles)
    if entry is None:
        return None

    stop = get_stop_loss(signal, candles)
    if stop is None:
        return None

    direction = signal.get("direction")
    target = get_take_profit(entry, stop, direction, rr_multiple)

    # Get future candles after entry
    future = candles.filter(pl.col("time") > signal["time"])

    result_r = evaluate_r_multiple(future, entry, stop, target, direction)

    if result_r is None:
        return None

    trade = {
        "trade_id": None,  # Will be assigned later
        "signal_id": signal["signal_id"],
        "pair": signal["pair"],
        "time": signal["time"],
        "entry": round(entry, 5),
        "stop": round(stop, 5),
        "target": round(target, 5),
        "direction": direction,
        "result_r": round(result_r, 2),
        "outcome": "WIN" if result_r > 0 else "LOSS",
        "rr_multiple": rr_multiple,
    }
    return trade