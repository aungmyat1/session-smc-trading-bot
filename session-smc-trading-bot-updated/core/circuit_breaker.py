"""
Circuit Breaker — per-strategy rate limiting and cooldown enforcement.

Tracks per strategy:
  - signals generated in the last hour (sliding window)
  - trades placed today
  - consecutive losses
  - cooldown expiry (triggered after max_losses hit)

Config example (from strategy_portfolio.yaml circuit_breaker section):
  LondonBreakout:
    max_signals_hour:  3
    max_trades_day:    3
    max_losses:        4
    cooldown_hours:    4
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional

_log = logging.getLogger("portfolio.circuit_breaker")

_DEFAULTS = {
    "max_signals_hour": 6,
    "max_trades_day":   4,
    "max_losses":       4,
    "cooldown_hours":   4,
}


class _StrategyState:
    __slots__ = (
        "signal_times", "trades_today", "consecutive_losses",
        "cooldown_until", "last_reset",
    )

    def __init__(self) -> None:
        self.signal_times:       list[datetime] = []
        self.trades_today:       int            = 0
        self.consecutive_losses: int            = 0
        self.cooldown_until:     Optional[datetime] = None
        self.last_reset:         str            = ""


class CircuitBreaker:
    def __init__(self, config: dict | None = None) -> None:
        self._cfg: dict[str, dict] = config or {}
        self._state: dict[str, _StrategyState] = {}

    def _state_for(self, name: str) -> _StrategyState:
        if name not in self._state:
            self._state[name] = _StrategyState()
        st = self._state[name]
        today = date.today().isoformat()
        if st.last_reset != today:
            st.trades_today       = 0
            st.consecutive_losses = 0
            st.cooldown_until     = None
            st.last_reset         = today
        return st

    def _cfg_for(self, name: str) -> dict:
        return {**_DEFAULTS, **self._cfg.get(name, {})}

    # ── Public API ─────────────────────────────────────────────────────────────

    def check(self, strategy_name: str) -> tuple[bool, str]:
        """Return (approved, reason). Call before routing a signal."""
        now = datetime.now(timezone.utc)
        st  = self._state_for(strategy_name)
        cfg = self._cfg_for(strategy_name)

        # Cooldown
        if st.cooldown_until and now < st.cooldown_until:
            remaining = int((st.cooldown_until - now).total_seconds() / 60)
            return False, f"cooldown — {remaining}min remaining"

        # Signals per hour (sliding window)
        window_start = now - timedelta(hours=1)
        st.signal_times = [t for t in st.signal_times if t > window_start]
        if len(st.signal_times) >= cfg["max_signals_hour"]:
            return False, f"signal rate limit ({cfg['max_signals_hour']}/hr)"

        # Trades per day
        if st.trades_today >= cfg["max_trades_day"]:
            return False, f"daily trade limit ({cfg['max_trades_day']}/day)"

        # Consecutive losses
        if st.consecutive_losses >= cfg["max_losses"]:
            cooldown = timedelta(hours=cfg["cooldown_hours"])
            st.cooldown_until = now + cooldown
            st.consecutive_losses = 0
            _log.warning("%s: max losses hit → cooldown %sh", strategy_name, cfg["cooldown_hours"])
            return False, f"max consecutive losses → cooldown {cfg['cooldown_hours']}h"

        return True, ""

    def record_signal(self, strategy_name: str) -> None:
        """Call when a signal passes initial checks — counts toward rate limit."""
        st = self._state_for(strategy_name)
        st.signal_times.append(datetime.now(timezone.utc))

    def record_trade(self, strategy_name: str, won: bool) -> None:
        """Call when a trade closes."""
        st = self._state_for(strategy_name)
        st.trades_today += 1
        if won:
            st.consecutive_losses = 0
        else:
            st.consecutive_losses += 1

    def reset_strategy(self, strategy_name: str) -> None:
        """Manual reset — for testing or admin override."""
        if strategy_name in self._state:
            del self._state[strategy_name]

    def status(self) -> dict:
        now = datetime.now(timezone.utc)
        return {
            name: {
                "signals_last_hour":   len([t for t in st.signal_times
                                            if t > now - timedelta(hours=1)]),
                "trades_today":        st.trades_today,
                "consecutive_losses":  st.consecutive_losses,
                "in_cooldown":         bool(st.cooldown_until and now < st.cooldown_until),
            }
            for name, st in self._state.items()
        }
