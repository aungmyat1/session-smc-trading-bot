"""
Signal Router — validates, deduplicates, and prioritises signals before execution.

Rules (in order):
  1. Reject expired signals (now - timestamp > ttl_seconds)
  2. Reject invalid geometry (BUY: sl < entry < tp | SELL: tp < entry < sl)
  3. Reject missing required fields
  4. Conflict: same symbol with BUY + SELL → reject both
  5. Same symbol + same direction → keep highest confidence only
  6. Sort approved signals by confidence desc (priority queue behaviour)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from shared.strategy_api import Signal

_log = logging.getLogger("portfolio.router")


def _parse_ts(ts: str) -> Optional[datetime]:
    try:
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


class SignalRouter:

    def route(self, signals: list[Signal]) -> list[Signal]:
        """
        Validate, resolve conflicts, deduplicate, and rank signals.
        Returns approved list sorted by confidence desc.
        """
        now      = datetime.now(timezone.utc)
        valid    = []
        rejected = []

        for sig in signals:
            ok, reason = self._validate(sig, now)
            if ok:
                valid.append(sig)
            else:
                rejected.append((sig.strategy_name, sig.symbol, reason))
                _log.debug("REJECTED %s %s — %s", sig.strategy_name, sig.symbol, reason)

        if rejected:
            _log.info("Router rejected %d signal(s): %s", len(rejected), rejected)

        resolved = self._resolve_conflicts(valid)
        return sorted(resolved, key=lambda s: s.confidence, reverse=True)

    # ── Validation ─────────────────────────────────────────────────────────────

    def _validate(self, sig: Signal, now: datetime) -> tuple[bool, str]:
        # Required fields
        if not sig.symbol:
            return False, "missing symbol"
        if sig.action not in ("BUY", "SELL", "CLOSE"):
            return False, f"invalid action={sig.action}"
        if sig.entry_price <= 0:
            return False, "entry_price <= 0"

        # TTL
        ts = _parse_ts(sig.timestamp)
        if ts is None:
            return False, "unparseable timestamp"
        age_s = (now - ts).total_seconds()
        if age_s > sig.ttl_seconds:
            return False, f"expired (age={age_s:.0f}s ttl={sig.ttl_seconds}s)"

        # Skip geometry for CLOSE signals
        if sig.action == "CLOSE":
            return True, ""

        # SL/TP geometry
        if sig.action == "BUY":
            if not (sig.stop_loss < sig.entry_price):
                return False, f"BUY: sl={sig.stop_loss} must be < entry={sig.entry_price}"
            if not (sig.take_profit > sig.entry_price):
                return False, f"BUY: tp={sig.take_profit} must be > entry={sig.entry_price}"
        else:  # SELL
            if not (sig.stop_loss > sig.entry_price):
                return False, f"SELL: sl={sig.stop_loss} must be > entry={sig.entry_price}"
            if not (sig.take_profit < sig.entry_price):
                return False, f"SELL: tp={sig.take_profit} must be < entry={sig.entry_price}"

        return True, ""

    # ── Conflict resolution ────────────────────────────────────────────────────

    def _resolve_conflicts(self, signals: list[Signal]) -> list[Signal]:
        # Group by symbol
        by_symbol: dict[str, list[Signal]] = {}
        for sig in signals:
            by_symbol.setdefault(sig.symbol, []).append(sig)

        approved: list[Signal] = []
        for symbol, group in by_symbol.items():
            actions = {s.action for s in group}

            # BUY and SELL both present → conflict → reject all for this symbol
            if "BUY" in actions and "SELL" in actions:
                _log.info("CONFLICT on %s: BUY+SELL both present → rejecting all", symbol)
                continue

            # Same direction → keep highest confidence only
            best = max(group, key=lambda s: s.confidence)
            approved.append(best)

        return approved
