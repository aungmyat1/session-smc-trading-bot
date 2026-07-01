"""Production runtime inventory facade.

This module is intentionally lightweight during the migration. It provides one
stable import location for future engine assembly while the active runtime still
lives in legacy top-level modules such as ``execution/`` and ``core/``.
"""

from __future__ import annotations

ACTIVE_RUNTIME_MODULES = (
    "execution.control_plane",
    "execution.execution_state",
    "execution.governance_guard",
    "execution.market_data",
    "execution.mt5_connector",
    "execution.order_manager",
    "execution.position_sizer",
    "execution.risk_manager",
    "execution.trade_manager",
)


def runtime_module_inventory() -> tuple[str, ...]:
    """Return the current production runtime module mapping."""

    return ACTIVE_RUNTIME_MODULES
