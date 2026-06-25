"""
Adaptive Session Engine v1 — SMC Session Strategy Adapter.

Wraps the existing strategy.session_liquidity.session_strategy module
and converts its Signal output to the AdaptiveSignal format.

PROTECTED SYSTEM: This module calls the existing strategy as a read-only
adapter. It NEVER modifies strategy/session_liquidity/**. The original
strategy logic is untouched.

Public API:
    generate_signals(candles_m15, candles_4h, symbol, config) -> list[AdaptiveSignal]
"""

from __future__ import annotations

from datetime import timezone

from adaptive.strategies import AdaptiveSignal

# Lazy import to avoid hard dependency if running tests without the full stack.
try:
    from strategy.session_liquidity.session_strategy import run_strategy, DEFAULT_CONFIG
    _STRATEGY_AVAILABLE = True
except ImportError:
    _STRATEGY_AVAILABLE = False
    DEFAULT_CONFIG = {}

_PIP = 0.0001  # pip size for EUR/GBP pairs


def generate_signals(
    candles_m15: list[dict],
    candles_4h: list[dict],
    symbol: str,
    config: dict | None = None,
) -> list[AdaptiveSignal]:
    """
    Run the existing SMC Session Liquidity strategy and adapt its signals.

    Args:
        candles_m15: M15 OHLCV dicts (open/high/low/close/volume, time in UTC).
        candles_4h:  H4 OHLCV dicts for HTF bias.
        symbol:      "EURUSD" | "GBPUSD".
        config:      Strategy config overrides (merged into DEFAULT_CONFIG).

    Returns:
        List of AdaptiveSignal objects — empty list if no signals.
        Returns empty list if the underlying strategy module is unavailable.
    """
    if not _STRATEGY_AVAILABLE:
        return []

    raw_signals = run_strategy(
        candles_m15=candles_m15,
        candles_4h=candles_4h,
        symbol=symbol,
        config=config,
    )

    results: list[AdaptiveSignal] = []
    for sig in raw_signals:
        ts = sig.timestamp
        if hasattr(ts, "isoformat"):
            ts_str = ts.astimezone(timezone.utc).isoformat()
        else:
            ts_str = str(ts)

        results.append(AdaptiveSignal(
            strategy  = "smc_session",
            pair      = symbol,
            direction = "LONG" if sig.side == "long" else "SHORT",
            entry_price = sig.entry,
            sl_price    = sig.stop_loss,
            tp_price    = sig.take_profit,
            session   = sig.session,
            timestamp = ts_str,
            reason    = sig.reason,
            metadata  = {
                "risk_pips":            sig.risk_pips,
                "reward_pips":          sig.reward_pips,
                "rr":                   sig.rr,
                "liquidity_swept":      True,   # sweep is a precondition in SA
                "structure_confirmed":  True,   # CHoCH+BOS+displacement required
            },
        ))

    return results


def is_available() -> bool:
    """True if the underlying strategy package is importable."""
    return _STRATEGY_AVAILABLE
