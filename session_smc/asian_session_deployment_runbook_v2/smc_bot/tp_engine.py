"""Simple R-multiple take-profit helper for the V2 runbook bundle."""

from __future__ import annotations


def build_plan(entry: float, sl: float, target_r: float = 5.0) -> dict:
    """Return a minimal TP plan compatible with the runbook tests."""
    risk = abs(entry - sl)
    if risk == 0:
        tp = entry
    elif sl < entry:
        tp = entry + risk * target_r
    else:
        tp = entry - risk * target_r
    return {
        "tp": round(tp, 6),
        "plan": [],
    }

