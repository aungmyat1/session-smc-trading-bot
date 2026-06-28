"""
Risk guards — fail-closed.

All guards deny on uncertainty. If state is ambiguous, the guard halts.

Guards:
    DailyLossGuard      — halt when daily loss ≥ max_daily_loss_r
    DrawdownGuard       — kill switch when equity ≤ peak × (1 - max_dd%)
    ConsecutiveLossGuard — halt when consecutive losses ≥ max
    KillSwitch          — emergency halt, blocks all write actions until reset

Usage::
    guard = DailyLossGuard(max_daily_loss_r=3.0)
    if guard.check(current_daily_loss_r):
        # Trading halted
        ...
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger(__name__)
_UTC = timezone.utc


class DailyLossGuard:
    """Halt trading when cumulative daily loss (in R) hits the limit."""

    def __init__(self, max_daily_loss_r: float = 3.0) -> None:
        self.max_daily_loss_r = max_daily_loss_r
        self._halted = False
        self._halt_reason = ""

    def check(self, current_daily_loss_r: float) -> bool:
        """
        Return True (halt) if current_daily_loss_r >= max.
        Fail-closed: any value >= threshold triggers halt.
        """
        if current_daily_loss_r >= self.max_daily_loss_r:
            if not self._halted:
                self._halted = True
                self._halt_reason = (
                    f"Daily loss {current_daily_loss_r:.2f}R "
                    f">= max {self.max_daily_loss_r}R"
                )
                logger.warning("DailyLossGuard HALT: %s", self._halt_reason)
            return True
        return False

    def reset(self) -> None:
        """Call at start of each trading day."""
        self._halted = False
        self._halt_reason = ""
        logger.info("DailyLossGuard reset.")

    @property
    def is_halted(self) -> bool:
        return self._halted

    @property
    def halt_reason(self) -> str:
        return self._halt_reason


class DrawdownGuard:
    """
    Kill switch when equity drawdown from peak exceeds threshold.

    Tracks peak equity internally; call update_equity() on each account update.
    """

    def __init__(
        self,
        peak_equity: float,
        max_drawdown_pct: float = 10.0,
    ) -> None:
        self._peak = peak_equity
        self.max_drawdown_pct = max_drawdown_pct
        self._halted = False

    def check(self, current_equity: float) -> bool:
        """Return True (kill) if drawdown from peak >= max_drawdown_pct."""
        if current_equity > self._peak:
            self._peak = current_equity
        drawdown_pct = (self._peak - current_equity) / self._peak * 100.0
        if drawdown_pct >= self.max_drawdown_pct:
            if not self._halted:
                self._halted = True
                logger.critical(
                    "DrawdownGuard KILL SWITCH: DD=%.2f%% >= max %.2f%%",
                    drawdown_pct, self.max_drawdown_pct,
                )
            return True
        return False

    def reset(self, new_peak: float) -> None:
        """Manual operator reset only — requires explicit new peak value."""
        self._peak = new_peak
        self._halted = False
        logger.info("DrawdownGuard reset. New peak: %.2f", new_peak)

    @property
    def peak_equity(self) -> float:
        return self._peak

    @property
    def is_active_kill(self) -> bool:
        return self._halted


class ConsecutiveLossGuard:
    """Halt when consecutive losses reach the limit. Win resets counter."""

    def __init__(self, max_consecutive_losses: int = 5) -> None:
        self.max_consecutive_losses = max_consecutive_losses
        self._count = 0
        self._halted = False

    def record_loss(self) -> bool:
        """Record a loss. Returns True if guard now halted."""
        self._count += 1
        if self._count >= self.max_consecutive_losses:
            self._halted = True
            logger.warning(
                "ConsecutiveLossGuard HALT: %d consecutive losses >= %d",
                self._count, self.max_consecutive_losses,
            )
        return self._halted

    def record_win(self) -> None:
        """Win resets consecutive loss counter."""
        if self._count > 0:
            logger.info(
                "ConsecutiveLossGuard: win after %d losses — counter reset.", self._count
            )
        self._count = 0
        self._halted = False

    def is_halted(self) -> bool:
        return self._halted

    def reset_day(self) -> None:
        """Call at start of new trading day."""
        self._halted = False
        logger.info("ConsecutiveLossGuard: day reset (count preserved at %d).", self._count)

    @property
    def count(self) -> int:
        return self._count


@dataclass
class KillSwitch:
    """
    Emergency kill switch — blocks ALL write actions once engaged.

    Can only be disengaged by explicit operator call with a reason.
    Fail-closed: if state is unknown, treat as engaged.
    """

    _engaged: bool = field(default=False, init=False)
    _reason: str = field(default="", init=False)
    _engaged_at: str = field(default="", init=False)

    def engage(self, reason: str) -> None:
        self._engaged = True
        self._reason = reason
        self._engaged_at = datetime.now(_UTC).isoformat()
        logger.critical("KillSwitch ENGAGED: %s", reason)

    def disengage(self, operator_reason: str) -> None:
        """Operator-only disengage with mandatory reason."""
        if not operator_reason:
            raise ValueError("Kill switch disengage requires an explicit operator_reason.")
        logger.warning("KillSwitch DISENGAGED by operator: %s", operator_reason)
        self._engaged = False
        self._reason = f"Disengaged: {operator_reason}"
        self._engaged_at = ""

    def is_engaged(self) -> bool:
        return self._engaged

    def guard_write(self) -> None:
        """Call before any write action. Raises if kill switch engaged."""
        if self._engaged:
            raise RuntimeError(
                f"Kill switch is engaged — all write actions blocked. "
                f"Reason: {self._reason}. Engaged at: {self._engaged_at}"
            )

    def status(self) -> dict:
        return {
            "engaged": self._engaged,
            "reason": self._reason,
            "engaged_at": self._engaged_at,
        }
