"""
Correlation Manager — blocks correlated positions from stacking risk.

Currency groups (configurable):
  EUR: EURUSD, EURJPY, EURGBP
  GBP: GBPUSD, GBPJPY, EURGBP
  JPY: USDJPY, EURJPY, GBPJPY

Rule: max one open position per currency group per direction.
Example: EURUSD BUY open → EURJPY BUY blocked (both in EUR group, both long EUR).
         EURUSD BUY open → EURJPY SELL allowed (opposite exposure).
"""

from __future__ import annotations

import logging

_log = logging.getLogger("portfolio.correlation")

_DEFAULT_GROUPS: dict[str, set[str]] = {
    "EUR": {"EURUSD", "EURJPY", "EURGBP"},
    "GBP": {"GBPUSD", "GBPJPY", "EURGBP"},
    "JPY": {"USDJPY", "EURJPY", "GBPJPY"},
}


class CorrelationManager:
    def __init__(self, groups: dict[str, list[str]] | None = None) -> None:
        if groups:
            self._groups = {k: set(v) for k, v in groups.items()}
        else:
            self._groups = _DEFAULT_GROUPS

    def get_groups(self, symbol: str) -> list[str]:
        """Return all currency group names this symbol belongs to."""
        return [name for name, members in self._groups.items() if symbol in members]

    def check(
        self,
        symbol: str,
        action: str,
        open_positions: dict[str, str],   # {symbol: action} of currently open trades
    ) -> tuple[bool, str]:
        """
        Returns (blocked, reason).

        Args:
            symbol:          candidate symbol to open
            action:          "BUY" or "SELL"
            open_positions:  dict mapping open symbol → its action
        """
        candidate_groups = self.get_groups(symbol)
        if not candidate_groups:
            return False, ""

        for grp in candidate_groups:
            members = self._groups[grp]
            for open_sym, open_action in open_positions.items():
                if open_sym == symbol:
                    continue
                if open_sym not in members:
                    continue
                if open_action == action:
                    reason = (f"{symbol} {action} blocked — {open_sym} {open_action} "
                              f"already open in {grp} group")
                    _log.debug(reason)
                    return True, reason

        return False, ""

    def filter_signals(
        self,
        signals: list,           # list[Signal]
        open_positions: dict[str, str],
    ) -> list:
        """Remove correlated signals from a candidate list (modifies order)."""
        approved = []
        pending_open: dict[str, str] = dict(open_positions)  # copy

        for sig in signals:  # assume already sorted by confidence desc
            blocked, reason = self.check(sig.symbol, sig.action, pending_open)
            if blocked:
                _log.info("CORR BLOCK %s %s — %s", sig.symbol, sig.action, reason)
                continue
            approved.append(sig)
            pending_open[sig.symbol] = sig.action  # treat approved as "virtually open"

        return approved
