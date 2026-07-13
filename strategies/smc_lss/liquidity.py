"""
SMC-LSS_v0 — Liquidity Sweep Engine.

detect_liquidity_sweep(candles, index, ...) -> LiquiditySweepEvent | None

Per config/strategies/SMC-LSS_v0.yaml `components.liquidity_sweep`:

    swing_lookback: 10
    sweep_atr_threshold: 0.25

Bullish sweep:
    low < previous N-bar swing low
    AND close > swept level
    AND wick penetration >= 0.25 * ATR(14)

Bearish sweep:
    high > previous N-bar swing high
    AND close < swept level
    AND wick penetration >= 0.25 * ATR(14)

"Previous N-bar swing low/high" is the min-low / max-high over the
`swing_lookback` CLOSED candles strictly before the evaluated candle
(candles[index - lookback : index]) — the candle at `index` itself is
never included in its own swing reference, so this cannot look ahead.

A candle satisfying both the bullish and bearish breach simultaneously is
a pathological/degenerate case (near-zero-range history); bullish is
checked first and wins the tie deterministically.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class LiquiditySweepEvent:
    timestamp: object
    symbol: str
    direction: str        # 'long' | 'short'
    swept_level: float
    atr: float
    penetration: float


def prior_swing_low(candles: list[dict], index: int, lookback: int) -> "float | None":
    """Min low over the `lookback` closed candles strictly before `index`."""
    if index < lookback:
        return None
    window = candles[index - lookback:index]
    if not window:
        return None
    return min(c["low"] for c in window)


def prior_swing_high(candles: list[dict], index: int, lookback: int) -> "float | None":
    """Max high over the `lookback` closed candles strictly before `index`."""
    if index < lookback:
        return None
    window = candles[index - lookback:index]
    if not window:
        return None
    return max(c["high"] for c in window)


def detect_liquidity_sweep(
    candles: list[dict],
    index: int,
    *,
    symbol: str,
    atr: "float | None",
    swing_lookback: int = 10,
    sweep_atr_threshold: float = 0.25,
) -> "LiquiditySweepEvent | None":
    """
    Evaluate candle `candles[index]` for a liquidity sweep against the
    prior `swing_lookback`-bar swing extreme.

    Args:
        candles:             chronological list of dicts with 'timestamp',
                              'high', 'low', 'close'.
        index:                position of the candle under evaluation.
        symbol:               instrument symbol, stored on the event.
        atr:                  ATR(14) at this bar (from displacement.wilder_atr).
        swing_lookback:       bars used to compute the prior swing extreme.
        sweep_atr_threshold:  minimum wick penetration, in ATR units.
    """
    if atr is None or atr <= 0:
        return None
    if index < 0 or index >= len(candles):
        return None

    candle = candles[index]
    low = float(candle["low"])
    high = float(candle["high"])
    close = float(candle["close"])

    swing_low = prior_swing_low(candles, index, swing_lookback)
    if swing_low is not None and low < swing_low and close > swing_low:
        penetration = swing_low - low
        if penetration >= sweep_atr_threshold * atr:
            return LiquiditySweepEvent(
                timestamp=candle.get("timestamp"),
                symbol=symbol,
                direction="long",
                swept_level=swing_low,
                atr=atr,
                penetration=penetration,
            )

    swing_high = prior_swing_high(candles, index, swing_lookback)
    if swing_high is not None and high > swing_high and close < swing_high:
        penetration = high - swing_high
        if penetration >= sweep_atr_threshold * atr:
            return LiquiditySweepEvent(
                timestamp=candle.get("timestamp"),
                symbol=symbol,
                direction="short",
                swept_level=swing_high,
                atr=atr,
                penetration=penetration,
            )

    return None
