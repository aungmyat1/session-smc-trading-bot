"""
Detects broker positions that disappeared between two ticks and matches them
back to their SQLite journal row, so the caller can feed a real trade outcome
into `execution/demo_risk_manager.py::record_result()` and
`core/portfolio_manager.py::record_close()` — both of which are otherwise dead
code (see SYSTEM2_MASTER_PLAN.md's Risk Engine / Position Management findings).

Matching key is (symbol, id == broker_order_id) — the same convention already
used by scripts/reconcile_positions.py. MetaAPI market-order results only carry
`orderId` (execution/vantage_demo_executor.py::place_order never captures a
separate `positionId`), so this is the best available match without a broker
protocol change; it is a pre-existing limitation, not introduced here.

Public API:
    diff_closed_positions(previous, current) -> list[dict]
    match_journal_trade(closed_position, open_trades) -> dict | None
"""

from __future__ import annotations

from typing import Any


def diff_closed_positions(previous: list[dict[str, Any]], current: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Positions present in `previous` whose id is no longer in `current`."""
    current_ids = {str(p.get("id")) for p in current if p.get("id")}
    return [p for p in previous if str(p.get("id") or "") and str(p.get("id")) not in current_ids]


def match_journal_trade(closed_position: dict[str, Any], open_trades: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Find the open journal row this closed broker position corresponds to, or None."""
    position_id = str(closed_position.get("id") or "")
    symbol = str(closed_position.get("symbol") or "")
    if not position_id:
        return None
    for trade in open_trades:
        if str(trade.get("broker_order_id") or "") == position_id and str(trade.get("symbol") or "") == symbol:
            return trade
    return None
