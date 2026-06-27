"""
Adaptive Session Engine v1 — Trade Router.

Routes signals through the full approval pipeline:
  Strategy Signal → Regime Filter → Signal Score → Risk Check → Approval

DEMO MODE ENFORCED: never places real orders.
Set DRY_RUN=true in environment (or pass dry_run=True) to operate.

Public API:
    route_signal(signal, candles, context, risk_state, config, dry_run) -> dict
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from adaptive.strategies import AdaptiveSignal
from adaptive.engine.regime_detector import detect_regime
from adaptive.engine.signal_scorer import score_signal
from adaptive.engine import risk_manager as _rm

_LOG_FILE = Path("logs/adaptive_engine.log")
_logger   = logging.getLogger("adaptive_engine.router")

# Regimes that block trading
_BLOCKED_REGIMES = {"UNSAFE"}

# Regimes each strategy is allowed in
_STRATEGY_REGIME_MAP: dict[str, set[str]] = {
    "smc_session":      {"RANGING", "BREAKOUT", "TRENDING"},
    "london_breakout":  {"BREAKOUT", "RANGING"},
    "ny_momentum":      {"TRENDING", "BREAKOUT"},
    "vwap_mean_reversion": {"RANGING"},
}


def _emit_log(entry: dict) -> None:
    """Append a JSON log line to the adaptive engine log file."""
    try:
        _LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with _LOG_FILE.open("a") as fh:
            fh.write(json.dumps(entry) + "\n")
    except OSError:
        _logger.warning("Could not write to %s", _LOG_FILE)


def route_signal(
    signal: AdaptiveSignal,
    candles: list[dict],
    context: dict,
    risk_state: dict,
    config: dict | None = None,
    dry_run: bool | None = None,
) -> dict:
    """
    Run a signal through the full approval pipeline.

    Args:
        signal:     AdaptiveSignal from any strategy.
        candles:    Recent OHLCV bars (oldest-first) for regime detection.
        context:    Runtime context — same dict as signal_scorer expects plus:
                      spread_pips, atr_pct, utc_hour, htf_bias, news_event
        risk_state: Live risk state dict (from risk_manager.new_state()).
        config:     Optional risk/filter config overrides.
        dry_run:    Force demo mode. Reads DRY_RUN env var if None.

    Returns:
        {
            "decision":         "APPROVED" | "REJECTED",
            "rejection_reason": str,
            "regime":           dict,
            "score_result":     dict,
            "risk_result":      dict,
            "timestamp":        str,
        }
    """
    if dry_run is None:
        dry_run = os.environ.get("DRY_RUN", "true").lower() not in ("false", "0", "no")

    ts = datetime.now(timezone.utc).isoformat()

    # ── Stage 1: Regime filter ─────────────────────────────────────────────
    spread_pips = float(context.get("spread_pips", 0.0))
    regime_result = detect_regime(candles, spread_pips=spread_pips)
    regime        = regime_result["regime"]

    if regime in _BLOCKED_REGIMES:
        reason = f"REGIME_BLOCKED: {regime}"
        _emit_log(_build_log(ts, signal, regime_result, {}, {}, "REJECTED", reason, dry_run))
        return _build_result("REJECTED", reason, regime_result, {}, {}, ts)

    allowed = _STRATEGY_REGIME_MAP.get(signal.strategy, set())
    if allowed and regime not in allowed:
        reason = f"REGIME_MISMATCH: {signal.strategy} not suited for {regime}"
        _emit_log(_build_log(ts, signal, regime_result, {}, {}, "REJECTED", reason, dry_run))
        return _build_result("REJECTED", reason, regime_result, {}, {}, ts)

    # ── Stage 2: Signal score ──────────────────────────────────────────────
    context_with_atr = {**context, "atr_pct": regime_result.get("atr_pct", 0.0)}
    score_result = score_signal(signal, context_with_atr)

    if not score_result["approved"]:
        reason = f"SCORE_REJECTED: {score_result['score']}/10 (need 7)"
        _emit_log(_build_log(ts, signal, regime_result, score_result, {}, "REJECTED", reason, dry_run))
        return _build_result("REJECTED", reason, regime_result, score_result, {}, ts)

    # ── Stage 3: Risk check ────────────────────────────────────────────────
    risk_result = _rm.check_risk(signal, risk_state, config)

    if not risk_result["approved"]:
        reason = risk_result["rejection_reason"]
        _emit_log(_build_log(ts, signal, regime_result, score_result, risk_result, "REJECTED", reason, dry_run))
        return _build_result("REJECTED", reason, regime_result, score_result, risk_result, ts)

    # ── APPROVED ──────────────────────────────────────────────────────────
    if dry_run:
        _emit_log(_build_log(ts, signal, regime_result, score_result, risk_result, "APPROVED", "", dry_run))
        return _build_result("APPROVED", "", regime_result, score_result, risk_result, ts)

    # Live execution would happen here — blocked until DRY_RUN=false and
    # CONFIRM token flow (per CLAUDE.md §6) is wired.
    reason = "LIVE_TRADING_NOT_ENABLED"
    _emit_log(_build_log(ts, signal, regime_result, score_result, risk_result, "REJECTED", reason, dry_run))
    return _build_result("REJECTED", reason, regime_result, score_result, risk_result, ts)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_result(
    decision: str,
    reason: str,
    regime: dict,
    score: dict,
    risk: dict,
    ts: str,
) -> dict:
    return {
        "decision":         decision,
        "rejection_reason": reason,
        "regime":           regime,
        "score_result":     score,
        "risk_result":      risk,
        "timestamp":        ts,
    }


def _build_log(
    ts: str,
    signal: AdaptiveSignal,
    regime: dict,
    score: dict,
    risk: dict,
    decision: str,
    reason: str,
    dry_run: bool,
) -> dict:
    return {
        "ts":       ts,
        "module":   "trade_router",
        "event":    "route_signal",
        "strategy": signal.strategy,
        "pair":     signal.pair,
        "direction": signal.direction,
        "session":  signal.session,
        "regime":   regime.get("regime", ""),
        "score":    score.get("score", -1),
        "decision": decision,
        "reason":   reason,
        "dry_run":  dry_run,
    }
