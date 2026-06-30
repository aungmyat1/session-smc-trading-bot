"""
D1 — Demo Execution Interface.

DRY_RUN=True by default. No real order placement.
Interface only — wire to MetaAPIClient when live promotion is approved
by owner via CONFIRM-LIVE-ON token (CLAUDE.md §6).

Public API:
    DemoExecutor(dry_run=True)
        async .execute(signal, account_balance) -> dict
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

from adaptive.strategies import AdaptiveSignal

_logger = logging.getLogger("adaptive.demo_executor")

_DRY_RUN_DEFAULT = os.environ.get("DRY_RUN", "true").lower() not in ("false", "0", "no")


class DemoExecutor:
    """
    Demo-mode execution interface.

    When dry_run=True (default): logs the order, returns a simulated result.
    When dry_run=False: reserved for future live wiring — still raises
    NotImplementedError until CONFIRM-LIVE-ON path is built.
    """

    def __init__(self, dry_run: bool | None = None) -> None:
        self.dry_run = dry_run if dry_run is not None else _DRY_RUN_DEFAULT

    async def execute(
        self, signal: AdaptiveSignal, account_balance: float = 0.0
    ) -> dict:
        """
        Simulate order execution.

        Args:
            signal:          Approved AdaptiveSignal to execute.
            account_balance: Current account balance (used for lot-size logging).

        Returns:
            {
                "order_id":   str,
                "dry_run":    bool,
                "symbol":     str,
                "direction":  str,
                "entry":      float,
                "sl":         float,
                "tp":         float,
                "timestamp":  str,
                "status":     "simulated" | "rejected",
            }
        """
        if not self.dry_run:
            raise NotImplementedError(
                "Live execution not enabled. Requires CONFIRM-LIVE-ON per CLAUDE.md §6."
            )

        ts = datetime.now(timezone.utc).isoformat()
        order_id = f"DRY-{signal.pair[:3]}-{ts[-8:].replace(':', '')}"

        _logger.info(
            "DRY_RUN order: %s %s %s @ %.5f SL=%.5f TP=%.5f",
            signal.direction,
            signal.pair,
            signal.strategy,
            signal.entry_price,
            signal.sl_price,
            signal.tp_price,
        )

        return {
            "order_id": order_id,
            "dry_run": True,
            "symbol": signal.pair,
            "direction": signal.direction,
            "entry": signal.entry_price,
            "sl": signal.sl_price,
            "tp": signal.tp_price,
            "timestamp": ts,
            "status": "simulated",
        }
