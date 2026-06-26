"""
Order manager — signal validation → position sizing → broker submission → logging.

MAX_OPEN_TRADES = 1: at most one position open per bot magic number at any time.
No re-entry after a signal is consumed. Every rejection is logged and returned.

Flow:
    signal_created (log)
        ↓
    circuit_breaker check
        ↓
    spread check (reject if unavailable / too wide)
        ↓
    duplicate position guard (MAX_OPEN_TRADES = 1)
        ↓
    position sizing (reject if SL out of range)
        ↓
    order_submitted (log)
        ↓
    place_order → broker
        ↓
    order_filled / order_rejected (log)
"""

import logging
from datetime import datetime, timezone

from execution.metaapi_client import MetaAPIClient
from execution.position_sizer import calculate_lots
from execution.risk_manager import RiskManager
from execution.trade_logger import TradeLogger

logger = logging.getLogger(__name__)

MAX_OPEN_TRADES: int = 1


class OrderManager:
    """
    Orchestrates the full order flow for one ST-A2 signal.

    The Signal dataclass (strategy.session_liquidity.entry_engine.Signal) does not
    carry `symbol` — the caller passes it explicitly, because run_strategy() is
    called per-symbol in the main loop.
    """

    def __init__(
        self,
        client: MetaAPIClient,
        risk: RiskManager,
        trade_logger: TradeLogger,
        config: dict,
    ) -> None:
        self._client = client
        self._risk = risk
        self._logger = trade_logger
        self._magic: dict[str, int] = config.get("magic_numbers", {})
        self._pip_value: dict[str, float] = config.get(
            "pip_value_per_lot", {"EURUSD": 10.0, "GBPUSD": 10.0}
        )

    async def process_signal(
        self,
        signal,
        symbol: str,
        equity: float,
    ) -> tuple[bool, str]:
        """
        Process one Signal through the full order flow.

        Args:
            signal:  Signal from strategy.session_liquidity.session_strategy.run_strategy()
                     Fields used: side, entry, stop_loss, take_profit, risk_pips,
                                  session, timestamp, reason
            symbol:  'EURUSD' | 'GBPUSD'
            equity:  current account equity

        Returns:
            (success, detail)
            success=True  → detail is the order_id string
            success=False → detail is a REASON string explaining the rejection
        """
        now = datetime.now(timezone.utc)
        sl_pips = signal.risk_pips

        # ── Step 1: log signal received ───────────────────────────────────────
        self._logger.signal_created(
            symbol=symbol,
            session=signal.session,
            side=signal.side,
            entry=signal.entry,
            sl=signal.stop_loss,
            tp=signal.take_profit,
            sl_pips=sl_pips,
            reason=signal.reason,
            signal_ts=signal.timestamp.isoformat(),
        )

        # ── Step 2: circuit breakers ──────────────────────────────────────────
        cb = self._risk.check_circuit_breakers(now)
        if cb.halted:
            reason = f"CIRCUIT_BREAKER:{cb.reason}"
            self._logger.order_rejected(symbol, reason, signal.side)
            logger.warning("[%s] Signal rejected: %s", symbol, reason)
            return False, reason

        # ── Step 3: spread check ──────────────────────────────────────────────
        spread_ok, spread_pips = await self._client.check_spread(symbol)
        if not spread_ok:
            reason = f"SPREAD_TOO_WIDE:{spread_pips:.1f}pip"
            self._logger.order_rejected(symbol, reason, signal.side)
            logger.warning("[%s] Signal rejected: %s", symbol, reason)
            return False, reason

        # ── Step 4: duplicate position guard ──────────────────────────────────
        magic = self._magic.get(symbol, 0)
        try:
            open_positions = await self._client.get_open_positions(magic=magic)
        except Exception as e:
            reason = f"GET_POSITIONS_FAILED:{e}"
            self._logger.order_rejected(symbol, reason, signal.side)
            self._logger.error(symbol, str(e), "get_open_positions")
            logger.warning("[%s] Signal rejected: %s", symbol, reason)
            return False, reason
        if len(open_positions) >= MAX_OPEN_TRADES:
            reason = f"MAX_OPEN_TRADES:{len(open_positions)}/{MAX_OPEN_TRADES}"
            self._logger.order_rejected(symbol, reason, signal.side)
            logger.info("[%s] Signal rejected: %s", symbol, reason)
            return False, reason

        # ── Step 5: position sizing ───────────────────────────────────────────
        pv = self._pip_value.get(symbol, 10.0)
        sizing = calculate_lots(
            equity=equity,
            sl_pips=sl_pips,
            symbol=symbol,
            risk_pct=self._risk.risk_pct,
            pip_value_per_lot=pv,
        )
        if not sizing.valid:
            reason = f"SIZING_REJECTED:{sizing.reject_reason}"
            self._logger.order_rejected(symbol, reason, signal.side)
            logger.warning("[%s] Signal rejected: %s", symbol, reason)
            return False, reason

        # ── Step 6: log order submission ──────────────────────────────────────
        self._logger.order_submitted(
            symbol=symbol,
            session=signal.session,
            direction=signal.side,
            volume=sizing.lots,
            sl=signal.stop_loss,
            tp=signal.take_profit,
            lots=sizing.lots,
            equity=equity,
            risk_pct=self._risk.risk_pct,
        )

        # ── Step 7: place order ───────────────────────────────────────────────
        try:
            result = await self._client.place_order(
                symbol=symbol,
                direction=signal.side,
                volume=sizing.lots,
                sl=signal.stop_loss,
                tp=signal.take_profit,
                magic=magic,
                comment=f"ST-A2-{signal.session[:3].upper()}",
            )
        except Exception as e:
            reason = f"ORDER_FAILED:{e}"
            self._logger.order_rejected(symbol, reason, signal.side)
            self._logger.error(symbol, str(e), "place_order")
            logger.exception("[%s] Order placement failed: %s", symbol, e)
            return False, reason

        # ── Step 8: log fill ──────────────────────────────────────────────────
        self._logger.order_filled(
            symbol=symbol,
            order_id=result.order_id,
            entry_price=result.entry_price,
            volume=result.volume,
            sl=result.sl,
            tp=result.tp,
            dry_run=result.dry_run,
        )

        logger.info(
            "Order %s: %s %s  vol=%.2f  id=%s",
            "DRY_RUN" if result.dry_run else "FILLED",
            signal.side.upper(), symbol, result.volume, result.order_id,
        )
        return True, result.order_id
