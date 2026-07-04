"""
Shared trade-close handling for every demo runner.

Detects broker positions that closed since the previous tick and feeds their
real outcome into the risk engine, portfolio manager, circuit breaker, and
trade journal. Extracted from scripts/run_st_a2_demo.py so scripts/run_portfolio.py
uses the exact same handling instead of a second, drifting copy (ROADMAP.md
Phase 1: "ensure identical trade-close handling and remove all hardcoded
trade outcomes").

Without this, record_result()/record_close() are never called from a real
close and every loss-limit / consecutive-loss / one-per-symbol guard silently
stops reflecting reality after the first trade (SYSTEM2_MASTER_PLAN.md Risk
Engine / Position Management findings).

Public API:
    async process_closed_positions(
        positions, risk_state, executor, telegram,
        portfolio_manager, circuit_breaker, journal_db,
    ) -> dict (updated risk_state)
"""

from __future__ import annotations

import logging
from typing import Any

from core.circuit_breaker import CircuitBreaker
from core.portfolio_manager import PortfolioManager
from core.trade_journal_db import TradeJournalDB
from execution.demo_risk_manager import record_result
from execution.position_close_detector import diff_closed_positions, match_journal_trade

_log = logging.getLogger("execution.close_reconciliation")


async def process_closed_positions(
    positions: list[dict[str, Any]],
    risk_state: dict,
    executor: Any,
    telegram: Any,
    portfolio_manager: PortfolioManager,
    circuit_breaker: CircuitBreaker,
    journal_db: TradeJournalDB,
) -> dict:
    """Diff `positions` against the last known snapshot in `risk_state` and
    process any that disappeared (closed) since. Mutates and returns `risk_state`.

    `telegram` may be None — alerts are skipped, not required.
    """
    previous = risk_state.get("_last_positions", [])
    closed = diff_closed_positions(previous, positions)
    risk_state["_last_positions"] = positions
    if not closed:
        return risk_state

    open_trades = journal_db.get_open_trades()
    try:
        balance = (await executor.get_account_info())["balance"]
    except Exception:
        balance = 0.0

    for position in closed:
        trade = match_journal_trade(position, open_trades)
        if trade is None:
            _log.warning(
                "Closed broker position %s (%s) has no matching OPEN journal trade — "
                "risk/portfolio state NOT updated for this close.",
                position.get("id"), position.get("symbol"),
            )
            if telegram is not None:
                await telegram.send_reconciliation_mismatch(
                    f"Unreconciled position close: {position.get('symbol')} {position.get('id')} "
                    "— no matching journal trade, risk engine not updated."
                )
            continue

        profit = float(position.get("profit") or 0.0)
        pnl_pct = (profit / balance) if balance else 0.0
        outcome = "WIN" if profit > 0 else "LOSS" if profit < 0 else "BREAKEVEN"
        risk_percentage = float(trade.get("risk_percentage") or 0.0)
        r_multiple = (pnl_pct / risk_percentage) if risk_percentage else 0.0
        close_price = position.get("current_price")
        if close_price is None:
            # No live price at close time available — fall back to the entry
            # price rather than fabricating one; this only affects the stored
            # close_price display field, not profit/r_multiple which come
            # straight from the broker's own reported profit.
            close_price = trade.get("entry_price") or 0.0

        journal_db.update_close(
            trade["id"],
            close_price=float(close_price or 0.0),
            profit_loss=profit,
            r_multiple=r_multiple,
            reason_for_exit="broker_position_closed",
        )
        risk_state = record_result(risk_state, outcome, pnl_pct)
        portfolio_manager.record_close(str(position.get("symbol") or trade.get("symbol") or ""), pnl_pct=pnl_pct)
        strategy_name = str(trade.get("strategy_name") or "")
        if strategy_name:
            # CircuitBreaker.record_trade() must reflect the real close outcome,
            # never a hardcoded won=True at open time — that would permanently
            # mask consecutive losses from ever cooling down.
            circuit_breaker.record_trade(strategy_name, won=(outcome == "WIN"))
        _log.info(
            "Trade closed: %s %s pnl=%.2f (%.3f%%) outcome=%s journal_id=%s halted=%s",
            trade.get("symbol"), position.get("id"), profit, pnl_pct * 100, outcome,
            trade["id"], risk_state.get("halted"),
        )
        if telegram is not None:
            await telegram.send_trade_close(
                symbol=str(trade.get("symbol") or position.get("symbol") or ""),
                direction=str(trade.get("direction") or ""),
                result_r=r_multiple,
                reason="broker_position_closed",
            )
    return risk_state
