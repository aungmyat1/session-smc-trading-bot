"""
Risk manager — lot sizing, position guards, circuit breakers.

State is persisted to logs/bot_state.json so circuit-breaker counts
survive bot restarts.

This module serves the legacy `bot.py` execution path through
`execution/order_manager.py`. The live `scripts/run_st_a2_demo.py` path uses
`execution/demo_risk_manager.py` instead.
"""

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

STATE_FILE = Path("logs/bot_state.json")


@dataclass
class CircuitBreakerResult:
    halted: bool
    reason: str = ""


@dataclass
class BotState:
    daily_loss_r: float = 0.0
    weekly_loss_r: float = 0.0
    monthly_loss_r: float = 0.0
    consecutive_losses: int = 0
    last_reset_date: str = ""
    last_reset_week: str = ""
    last_reset_month: str = ""
    halted: bool = False
    halt_reason: str = ""

    def to_dict(self) -> dict:
        return {
            "daily_loss_r": self.daily_loss_r,
            "weekly_loss_r": self.weekly_loss_r,
            "monthly_loss_r": self.monthly_loss_r,
            "consecutive_losses": self.consecutive_losses,
            "last_reset_date": self.last_reset_date,
            "last_reset_week": self.last_reset_week,
            "last_reset_month": self.last_reset_month,
            "halted": self.halted,
            "halt_reason": self.halt_reason,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "BotState":
        return cls(
            daily_loss_r=d.get("daily_loss_r", 0.0),
            weekly_loss_r=d.get("weekly_loss_r", 0.0),
            monthly_loss_r=d.get("monthly_loss_r", 0.0),
            consecutive_losses=d.get("consecutive_losses", 0),
            last_reset_date=d.get("last_reset_date", ""),
            last_reset_week=d.get("last_reset_week", ""),
            last_reset_month=d.get("last_reset_month", ""),
            halted=d.get("halted", False),
            halt_reason=d.get("halt_reason", ""),
        )


class RiskManager:
    def __init__(self, config: dict):
        r = config["risk"]
        self.risk_pct: float = r["risk_per_trade_pct"]
        self.max_open_trades: int = r["max_open_trades"]
        self.max_pair_exposure: int = r["max_pair_exposure"]
        self.max_daily_loss_r: float = r["max_daily_loss_r"]
        self.max_weekly_loss_r: float = r["max_weekly_loss_r"]
        # Optional — defaults to "disabled" (no configured limit) so existing
        # configs/tests that predate the monthly limit keep prior behavior.
        # config/strategy_portfolio.yaml's `monthly_loss_limit_pct` is a
        # portfolio-level percentage figure in a different unit system (equity
        # %, not R-multiples) and is not auto-converted here — set
        # `max_monthly_loss_r` explicitly in config["risk"] to enable this gate.
        self.max_monthly_loss_r: float = r.get("max_monthly_loss_r", float("inf"))
        self.max_consecutive_losses: int = r["max_consecutive_losses"]
        self.min_lot: float = r["min_lot"]
        self.max_lot: float = r["max_lot"]
        self.pip_value_per_lot: dict = config["pip_value_per_lot"]
        self._state = self._load_state()

    # ── State persistence ────────────────────────────────────────────────────

    def _load_state(self) -> BotState:
        if STATE_FILE.exists():
            try:
                data = json.loads(STATE_FILE.read_text())
                state = BotState.from_dict(data)
                logger.info("Bot state loaded: daily_loss=%.2fR consec=%d halted=%s",
                            state.daily_loss_r, state.consecutive_losses, state.halted)
                return state
            except Exception as e:
                logger.warning("Could not parse state file, resetting: %s", e)
        return BotState()

    def _save_state(self) -> None:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(self._state.to_dict(), indent=2))

    # ── Daily / weekly resets ────────────────────────────────────────────────

    def _maybe_reset(self, now: Optional[datetime] = None) -> None:
        now = now or datetime.now(timezone.utc)
        today = now.strftime("%Y-%m-%d")
        week = now.strftime("%Y-W%W")
        month = now.strftime("%Y-%m")

        if self._state.last_reset_date != today:
            self._state.daily_loss_r = 0.0
            self._state.last_reset_date = today
            # Only clear the daily halt if the halt was daily-loss triggered.
            if self._state.halt_reason == "MAX_DAILY_LOSS":
                self._state.halted = False
                self._state.halt_reason = ""
            logger.info("Daily state reset for %s", today)

        # NOTE: unlike MAX_DAILY_LOSS, MAX_WEEKLY_LOSS and MAX_MONTHLY_LOSS
        # halts are intentionally NOT auto-cleared on their own period reset
        # (see tests/test_order_manager.py::TestCircuitBreakerRejection —
        # "MAX_WEEKLY_LOSS is not auto-cleared on daily reset"). Only the
        # running counters reset; clearing the halt itself requires manual
        # intervention. MAX_MONTHLY_LOSS follows the same pattern as
        # MAX_WEEKLY_LOSS for consistency.
        if self._state.last_reset_week != week:
            self._state.weekly_loss_r = 0.0
            self._state.last_reset_week = week
            logger.info("Weekly state reset for %s", week)

        if self._state.last_reset_month != month:
            self._state.monthly_loss_r = 0.0
            self._state.last_reset_month = month
            logger.info("Monthly state reset for %s", month)

        self._save_state()

    # ── Lot sizing ───────────────────────────────────────────────────────────

    def calculate_lot_size(self, balance: float, sl_pips: float, symbol: str) -> float:
        """Return lot size such that sl_pips × lot = risk_per_trade_pct of balance."""
        if sl_pips <= 0:
            raise ValueError(f"sl_pips must be > 0, got {sl_pips}")
        pv = self.pip_value_per_lot.get(symbol, 10.0)
        risk_amount = balance * (self.risk_pct / 100.0)
        lot = risk_amount / (sl_pips * pv)
        lot = round(lot, 2)
        lot = max(self.min_lot, min(self.max_lot, lot))
        return lot

    # ── Position guards ──────────────────────────────────────────────────────

    def can_open_position(self, symbol: str, open_positions: list) -> tuple[bool, str]:
        """Check max-trades and per-pair limits. Returns (allowed, reason)."""
        total = len(open_positions)
        if total >= self.max_open_trades:
            return False, f"MAX_OPEN_TRADES ({total}/{self.max_open_trades})"

        pair_count = sum(1 for p in open_positions if p.symbol == symbol)
        if pair_count >= self.max_pair_exposure:
            return False, f"MAX_PAIR_EXPOSURE for {symbol} ({pair_count}/{self.max_pair_exposure})"

        return True, ""

    # ── Circuit breakers ─────────────────────────────────────────────────────

    def check_circuit_breakers(self, now: Optional[datetime] = None) -> CircuitBreakerResult:
        self._maybe_reset(now)
        if self._state.halted:
            return CircuitBreakerResult(halted=True, reason=self._state.halt_reason)
        return CircuitBreakerResult(halted=False)

    def record_trade_result(self, result_r: float, now: Optional[datetime] = None) -> None:
        """Update running loss counters. Call after every closed trade."""
        self._maybe_reset(now)

        if result_r < 0:
            loss = abs(result_r)
            self._state.daily_loss_r += loss
            self._state.weekly_loss_r += loss
            self._state.monthly_loss_r += loss
            self._state.consecutive_losses += 1

            if self._state.daily_loss_r >= self.max_daily_loss_r:
                self._state.halted = True
                self._state.halt_reason = "MAX_DAILY_LOSS"
                logger.warning("CIRCUIT BREAKER: max daily loss reached (%.2fR)", self._state.daily_loss_r)

            elif self._state.weekly_loss_r >= self.max_weekly_loss_r:
                self._state.halted = True
                self._state.halt_reason = "MAX_WEEKLY_LOSS"
                logger.warning("CIRCUIT BREAKER: max weekly loss reached (%.2fR)", self._state.weekly_loss_r)

            elif self._state.monthly_loss_r >= self.max_monthly_loss_r:
                self._state.halted = True
                self._state.halt_reason = "MAX_MONTHLY_LOSS"
                logger.warning("CIRCUIT BREAKER: max monthly loss reached (%.2fR)", self._state.monthly_loss_r)

            elif self._state.consecutive_losses >= self.max_consecutive_losses:
                self._state.halted = True
                self._state.halt_reason = "MAX_CONSECUTIVE_LOSSES"
                logger.warning("CIRCUIT BREAKER: %d consecutive losses", self._state.consecutive_losses)
        else:
            self._state.consecutive_losses = 0

        self._save_state()

    # ── Accessors ─────────────────────────────────────────────────────────────

    @property
    def state(self) -> BotState:
        return self._state

    def summary(self) -> str:
        s = self._state
        monthly_limit = "inf" if self.max_monthly_loss_r == float("inf") else f"{self.max_monthly_loss_r}"
        return (
            f"daily={s.daily_loss_r:.2f}R/{self.max_daily_loss_r}R  "
            f"weekly={s.weekly_loss_r:.2f}R/{self.max_weekly_loss_r}R  "
            f"monthly={s.monthly_loss_r:.2f}R/{monthly_limit}R  "
            f"consec={s.consecutive_losses}/{self.max_consecutive_losses}  "
            f"halted={s.halted}"
        )
