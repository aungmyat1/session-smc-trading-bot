"""
Adaptive Session Engine v1 — Unified Risk Manager.

Enforces per-trade risk limits, daily caps, consecutive-loss halts,
and correlated-position guards. Stateless across calls — caller
must pass and persist the state dict.

NOTE: This is isolated from execution/risk_manager.py which manages
the live bot. This manager is demo/shadow-mode only.

Public API:
    new_state()            -> dict
    check_risk(signal, state, config) -> dict
    record_trade(result, state, config) -> dict
"""

from __future__ import annotations

from adaptive.strategies import AdaptiveSignal

# ── Defaults (overridden by config/adaptive_engine.yaml at runtime) ──────────

DEFAULT_CONFIG = {
    "risk_per_trade": 0.005,  # 0.5% of account
    "daily_loss_limit": 0.015,  # 1.5%
    "max_trades_per_day": 6,
    "max_consecutive_losses": 3,
    # Correlated pairs: LONG on both simultaneously is blocked
    "correlated_pairs": [
        ("EURUSD", "GBPUSD"),
    ],
}

# Correlated direction pairs (both LONG or both SHORT are correlated)
_SAME_DIRECTION_BLOCKED = {"LONG"}  # LONG EURUSD + LONG GBPUSD blocked


def new_state() -> dict:
    """Return a fresh intra-day risk state."""
    return {
        "daily_loss_pct": 0.0,
        "trades_today": 0,
        "consecutive_losses": 0,
        "open_positions": [],  # list of {"pair": str, "direction": str}
        "halted": False,
        "halt_reason": "",
    }


def _correlated(
    signal: AdaptiveSignal, open_positions: list[dict], config: dict
) -> bool:
    """True if adding this signal would create a correlated position."""
    corr_groups: list[tuple] = config.get(
        "correlated_pairs", DEFAULT_CONFIG["correlated_pairs"]
    )
    for open_pos in open_positions:
        if open_pos["direction"] != signal.direction:
            continue
        if signal.direction not in _SAME_DIRECTION_BLOCKED:
            continue
        pair_a, pair_b = open_pos["pair"], signal.pair
        for group in corr_groups:
            if pair_a in group and pair_b in group and pair_a != pair_b:
                return True
    return False


def check_risk(signal: AdaptiveSignal, state: dict, config: dict | None = None) -> dict:
    """
    Evaluate whether a new signal passes all risk guards.

    Args:
        signal: AdaptiveSignal to evaluate.
        state:  Current risk state dict (from new_state() or persisted).
        config: Risk config overrides. Falls back to DEFAULT_CONFIG.

    Returns:
        {
            "approved":       bool,
            "rejection_reason": str,  # "" if approved
            "checks": {name: bool},
        }
    """
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    checks: dict[str, bool] = {}

    # 1 — daily halt
    checks["not_halted"] = not state.get("halted", False)

    # 2 — daily loss cap
    checks["daily_loss_ok"] = state.get("daily_loss_pct", 0.0) < cfg["daily_loss_limit"]

    # 3 — trade count cap
    checks["trade_count_ok"] = state.get("trades_today", 0) < cfg["max_trades_per_day"]

    # 4 — consecutive loss limit
    checks["consec_loss_ok"] = (
        state.get("consecutive_losses", 0) < cfg["max_consecutive_losses"]
    )

    # 5 — correlation guard
    checks["no_correlation"] = not _correlated(
        signal, state.get("open_positions", []), cfg
    )

    approved = all(checks.values())
    rejection_reason = ""
    if not approved:
        failed = [k for k, v in checks.items() if not v]
        rejection_reason = "RISK_BLOCKED: " + ", ".join(failed)

    return {
        "approved": approved,
        "rejection_reason": rejection_reason,
        "checks": checks,
    }


def record_trade(result: dict, state: dict, config: dict | None = None) -> dict:
    """
    Update risk state after a trade closes.

    Args:
        result: {
            "pair":       str,
            "direction":  str,
            "pnl_pct":    float,  # signed P&L as fraction of account
            "outcome":    "WIN" | "LOSS" | "BREAKEVEN",
        }
        state:  Current risk state dict (mutated and returned).
        config: Risk config overrides.

    Returns:
        Updated state dict.
    """
    cfg = {**DEFAULT_CONFIG, **(config or {})}

    pnl = result.get("pnl_pct", 0.0)
    outcome = result.get("outcome", "LOSS")

    state["daily_loss_pct"] = state.get("daily_loss_pct", 0.0) + (
        -pnl if pnl < 0 else 0.0
    )
    state["trades_today"] = state.get("trades_today", 0) + 1

    if outcome == "LOSS":
        state["consecutive_losses"] = state.get("consecutive_losses", 0) + 1
    else:
        state["consecutive_losses"] = 0

    # Remove closed position from open list
    pair = result.get("pair", "")
    direction = result.get("direction", "")
    open_pos = state.get("open_positions", [])
    state["open_positions"] = [
        p for p in open_pos if not (p["pair"] == pair and p["direction"] == direction)
    ]

    # Engage halt if thresholds breached
    if state["daily_loss_pct"] >= cfg["daily_loss_limit"]:
        state["halted"] = True
        state["halt_reason"] = "DAILY_LOSS_LIMIT_HIT"
    elif state["consecutive_losses"] >= cfg["max_consecutive_losses"]:
        state["halted"] = True
        state["halt_reason"] = "CONSECUTIVE_LOSS_LIMIT_HIT"

    return state


def register_open_position(signal: AdaptiveSignal, state: dict) -> dict:
    """Record that a position was opened (after approval). Returns updated state."""
    state.setdefault("open_positions", []).append(
        {
            "pair": signal.pair,
            "direction": signal.direction,
        }
    )
    return state


def reset_daily(state: dict) -> dict:
    """Reset intra-day counters at the start of a new trading day."""
    state["daily_loss_pct"] = 0.0
    state["trades_today"] = 0
    state["consecutive_losses"] = 0
    state["halted"] = False
    state["halt_reason"] = ""
    return state
