"""Minimal HTF bias helper used by the V2 runbook bundle.

Tests patch `get_bias()` directly, so the default implementation only needs to
be safe and deterministic when invoked outside the test suite.
"""

from __future__ import annotations

from typing import Any


def get_bias(df_4h: Any) -> str:
    """Return a coarse bullish/bearish/neutral bias from price drift."""
    if df_4h is None:
        return "neutral"

    closes: list[float] = []
    if hasattr(df_4h, "__getitem__"):
        try:
            closes = [float(x) for x in df_4h["close"].tolist()]
        except Exception:
            closes = []

    if len(closes) < 2:
        return "neutral"

    first = closes[0]
    last = closes[-1]
    if last > first:
        return "bullish"
    if last < first:
        return "bearish"
    return "neutral"
