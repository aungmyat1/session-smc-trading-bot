"""
Portfolio Manager — multi-strategy signal routing and risk coordination.

Responsibilities:
  1. Filter signals by enabled strategies and per-strategy min_confidence
  2. Deduplicate: one open position per symbol
  3. Correlation filter: same direction on correlated pairs → keep highest confidence only
  4. Enforce max daily trades and max open positions
  5. Rank approved signals by confidence (descending)

Does NOT know about SMC, breakout rules, indicators, or broker details.
"""

from __future__ import annotations

from datetime import date
from typing import List, Optional

from shared.strategy_api import Signal

# Risk tiers — risk_pct applied per trade (% of account)
RISK_TIERS: dict[str, float] = {
    "tier1": 0.30,   # validated: ST-A2
    "tier2": 0.20,   # conditionally validated: LondonBreakout, NYMomentum
    "tier3": 0.10,   # unvalidated / shadow: new strategies
}

_STRATEGY_TIER: dict[str, str] = {
    "ST-A2":          "tier1",
    "LondonBreakout": "tier2",
    "NYMomentum":     "tier2",
    "AdaptiveSMC":    "tier3",
    "VWAPMeanReversion": "tier3",
    "VWAPBreakout":   "tier3",
}

_DEFAULT_CONFIG = {
    "portfolio": {
        "max_trades_per_day":    8,
        "max_open_positions":    3,
        "daily_loss_limit_pct":  2.0,
        "weekly_loss_limit_pct": 5.0,
        "monthly_loss_limit_pct":8.0,
        "min_confidence":        0.6,
    },
    "correlation_groups": [["EURUSD", "GBPUSD"]],
    "strategies": {},
}


class PortfolioManager:
    def __init__(self, config: dict | None = None) -> None:
        self._cfg      = config or _DEFAULT_CONFIG
        self._pcfg     = self._cfg.get("portfolio", _DEFAULT_CONFIG["portfolio"])
        self._strat_cfg: dict = self._cfg.get("strategies", {})
        self._corr_groups: list[list[str]] = self._cfg.get("correlation_groups", [])

        self._trades_today:    int       = 0
        self._open_symbols:    set[str]  = set()
        self._last_reset:      str       = ""
        self._daily_pnl_pct:   float     = 0.0
        self._weekly_pnl_pct:  float     = 0.0
        self._monthly_pnl_pct: float     = 0.0

    # ── Public API ─────────────────────────────────────────────────────────────

    def evaluate(self, signals: list[Signal]) -> list[Signal]:
        """
        Filter, deduplicate, correlate, and rank a batch of signals.
        Returns approved signals sorted by confidence desc.
        """
        self._maybe_reset_daily()

        # 1. Filter by strategy enabled + per-strategy min_confidence
        filtered = [s for s in signals if self._strategy_allowed(s)]

        # 2. Deduplicate by symbol already open
        filtered = [s for s in filtered if s.symbol not in self._open_symbols]

        # 3. Correlation filter
        filtered = self._apply_correlation_filter(filtered)

        # 4. Enforce global min_confidence
        min_conf = self._pcfg.get("min_confidence", 0.6)
        filtered = [s for s in filtered if s.confidence >= min_conf]

        # 5. Daily trade cap
        cap     = self._pcfg.get("max_trades_per_day", 8)
        slots   = cap - self._trades_today
        filtered = filtered[:max(0, slots)]

        # 6. Open positions cap
        pos_cap   = self._pcfg.get("max_open_positions", 3)
        pos_slots = pos_cap - len(self._open_symbols)
        filtered  = filtered[:max(0, pos_slots)]

        # 7. Rank by confidence desc
        return sorted(filtered, key=lambda s: s.confidence, reverse=True)

    def record_trade(self, signal: Signal) -> None:
        """Call after an order is placed to track state."""
        self._trades_today  += 1
        self._open_symbols.add(signal.symbol)

    def record_close(self, symbol: str, pnl_pct: float = 0.0) -> None:
        """Call when a position closes."""
        self._open_symbols.discard(symbol)
        self._daily_pnl_pct   += pnl_pct
        self._weekly_pnl_pct  += pnl_pct
        self._monthly_pnl_pct += pnl_pct

    def get_risk_pct(self, strategy_name: str) -> float:
        """Return risk % for this strategy based on its tier."""
        tier = _STRATEGY_TIER.get(strategy_name, "tier3")
        return RISK_TIERS[tier]

    def is_daily_loss_hit(self) -> bool:
        limit = self._pcfg.get("daily_loss_limit_pct", 2.0) / 100
        return self._daily_pnl_pct <= -limit

    def is_weekly_loss_hit(self) -> bool:
        limit = self._pcfg.get("weekly_loss_limit_pct", 5.0) / 100
        return self._weekly_pnl_pct <= -limit

    def is_monthly_loss_hit(self) -> bool:
        limit = self._pcfg.get("monthly_loss_limit_pct", 8.0) / 100
        return self._monthly_pnl_pct <= -limit

    def any_loss_limit_hit(self) -> bool:
        return self.is_daily_loss_hit() or self.is_weekly_loss_hit() or self.is_monthly_loss_hit()

    def export_state(self) -> dict:
        """Serialize the in-memory counters this instance tracks — used to persist
        state across process restarts (see scripts/run_st_a2_demo.py)."""
        return {
            "trades_today":    self._trades_today,
            "open_symbols":    sorted(self._open_symbols),
            "last_reset":      self._last_reset,
            "daily_pnl_pct":   self._daily_pnl_pct,
            "weekly_pnl_pct":  self._weekly_pnl_pct,
            "monthly_pnl_pct": self._monthly_pnl_pct,
        }

    def load_state(self, data: dict) -> None:
        """Restore counters previously produced by `export_state()`."""
        self._trades_today    = data.get("trades_today", 0)
        self._open_symbols    = set(data.get("open_symbols", []))
        self._last_reset      = data.get("last_reset", "")
        self._daily_pnl_pct   = data.get("daily_pnl_pct", 0.0)
        self._weekly_pnl_pct  = data.get("weekly_pnl_pct", 0.0)
        self._monthly_pnl_pct = data.get("monthly_pnl_pct", 0.0)

    def stats(self) -> dict:
        return {
            "trades_today":       self._trades_today,
            "open_symbols":       sorted(self._open_symbols),
            "daily_pnl_pct":      round(self._daily_pnl_pct * 100, 3),
            "weekly_pnl_pct":     round(self._weekly_pnl_pct * 100, 3),
            "monthly_pnl_pct":    round(self._monthly_pnl_pct * 100, 3),
            "loss_limit_hit":     self.is_daily_loss_hit(),
            "weekly_limit_hit":   self.is_weekly_loss_hit(),
            "monthly_limit_hit":  self.is_monthly_loss_hit(),
        }

    # ── Internal ───────────────────────────────────────────────────────────────

    def _strategy_allowed(self, signal: Signal) -> bool:
        cfg = self._strat_cfg.get(signal.strategy_name, {})
        if not cfg.get("enabled", True):
            return False
        min_conf = cfg.get("min_confidence", self._pcfg.get("min_confidence", 0.6))
        if signal.confidence < min_conf:
            return False
        allowed_pairs = cfg.get("pairs", [])
        if allowed_pairs and signal.symbol not in allowed_pairs:
            return False
        return True

    def _apply_correlation_filter(self, signals: list[Signal]) -> list[Signal]:
        """
        Within each correlation group: if two signals have the same direction,
        keep only the one with highest confidence.
        """
        if not signals or not self._corr_groups:
            return signals

        approved: list[Signal] = []
        direction_seen: dict[frozenset, Signal] = {}  # group_key → best signal so far

        for sig in sorted(signals, key=lambda s: s.confidence, reverse=True):
            group_key = self._group_key(sig.symbol)
            if group_key is None:
                approved.append(sig)
                continue

            # Compose key: group + direction
            dir_key = (group_key, sig.action)
            if dir_key not in direction_seen:
                direction_seen[dir_key] = sig
                approved.append(sig)
            # else: lower-confidence duplicate in same group+direction → drop

        return approved

    def _group_key(self, symbol: str) -> Optional[frozenset]:
        for group in self._corr_groups:
            if symbol in group:
                return frozenset(group)
        return None

    def _maybe_reset_daily(self) -> None:
        today = date.today().isoformat()
        if self._last_reset != today:
            self._trades_today = 0
            self._daily_pnl_pct = 0.0
            self._last_reset = today
