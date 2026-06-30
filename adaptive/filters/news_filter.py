"""
S3 — News Filter (stub).

Returns safe_to_trade=True for all symbols until a live news source
is connected. Replace _fetch_live_events() with a real feed to activate.

Public API:
    NewsFilter()
        .is_safe(symbol) -> {"safe_to_trade": bool, "source": str, "reason": str}
"""

from __future__ import annotations

import logging

_logger = logging.getLogger("adaptive.news_filter")


class NewsFilter:
    """
    Stub news filter. Always clears unless overridden.

    To wire a real feed:
      1. Override _fetch_live_events() to return active high-impact events.
      2. Set self._live = True in __init__ after the feed connects.
    """

    def __init__(self) -> None:
        self._live = False  # flip to True when real feed is wired
        self._blocked_symbols: set[str] = set()

    def is_safe(self, symbol: str) -> dict:
        """
        Check whether it is safe to trade the symbol right now.

        Returns:
            {
                "safe_to_trade": bool,
                "source":        "stub" | "live",
                "reason":        str,
            }
        """
        if not self._live:
            return {
                "safe_to_trade": True,
                "source": "stub",
                "reason": "news_filter_stub",
            }

        # Live path (not yet active)
        events = self._fetch_live_events(symbol)
        if events:
            _logger.warning("News block: %s events=%s", symbol, events)
            return {"safe_to_trade": False, "source": "live", "reason": str(events)}
        return {"safe_to_trade": True, "source": "live", "reason": ""}

    def block(self, symbol: str) -> None:
        """Manually block a symbol (testing / override)."""
        self._blocked_symbols.add(symbol)

    def unblock(self, symbol: str) -> None:
        self._blocked_symbols.discard(symbol)

    # ── Extension point ───────────────────────────────────────────────────────

    def _fetch_live_events(self, symbol: str) -> list[str]:
        """
        Override this to return a list of active high-impact event names
        for the given symbol's currencies. Return [] if clear.
        """
        if symbol in self._blocked_symbols:
            return [f"manual_block:{symbol}"]
        return []
