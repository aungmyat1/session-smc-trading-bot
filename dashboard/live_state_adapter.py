"""
Assembles a `LiveDashboardState`-shaped payload (per the Gai dashboard's
`src/types.ts`) from real System 2 services, for `GET /api/new-dashboard/live-state`.

This is deliberately NOT mounted at `/api/status` — that path already exists twice
(`dashboard/app.py::api_status` and `dashboard/status_server.py`) with an unrelated
SVOS/EVF-summary contract. See docs/dashboard/DASHBOARD_BACKEND_MAPPING.md.

Fields with no real backend source today (SMC pipeline checklist, active OB/FVG
objects, HTF bias/swing/ATR, signal rejections, MAE/MFE/slippage-latency, CPU/RAM/
disk, Redis) are returned as explicit neutral placeholders, not fabricated values,
and listed in the top-level `unavailable` key so a consumer can render an honest
"not available" state instead of trusting them as live data.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from dashboard import live_dashboard_service, strategy_service
from dashboard.control_state import load_control_state
import scripts.health_check as health_check
from core.trade_journal_db import TradeJournalDB

_PIPELINE_STAGES = [
    "htfBias", "liquiditySweep", "choch", "bos", "orderBlock",
    "fvg", "confluence", "killZone", "spread", "riskCheck",
    "positionSize", "ready",
]

_HEALTH_STATUS_MAP = {
    "PASS": "CONNECTED",
    "READY": "ACTIVE",
    "SHADOW": "ACTIVE",
    "WARN": "DEGRADED",
    "FAIL": "DOWN",
    "BLOCKED": "DOWN",
    "CONNECTED": "CONNECTED",
    "DEGRADED": "DEGRADED",
    "DISCONNECTED": "DOWN",
    "UNCONFIGURED": "DOWN",
    "N/A": "N/A",
}

_UNAVAILABLE_FIELDS = [
    "pairs[].trend", "pairs[].htfBias", "pairs[].swingHigh", "pairs[].swingLow",
    "pairs[].atr", "pairs[].pipeline (not instrumented by any strategy adapter)",
    "pairs[].activeObjects", "rejections (no strategy emits rejection reasons today)",
    "activeTrade (no pending-trade projection concept in current execution pipeline)",
    "analytics.signalsQualified", "analytics.signalsRejected",
    "history[].mae", "history[].mfe", "history[].latency", "history[].realRr",
    "systemResources (no resource-monitoring code exists)",
    "activeDeployments (strategy_catalog.yaml and strategy_portfolio.yaml are unsynced — see mapping doc)",
    "health.redis (no Redis in this architecture)", "health.websocket (no WS server exists)",
    "strategyPackages[].signature", "strategyPackages[].lastSignalTime",
    "strategyPackages[].entryFrequency", "strategyPackages[].latency",
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _health_status(raw_status: str) -> str:
    return _HEALTH_STATUS_MAP.get(str(raw_status).upper(), "UNKNOWN")


def _service_health(name: str, status: str, latency: float = -1, heartbeat: str = "") -> dict[str, Any]:
    return {"name": name, "status": _health_status(status), "latency": latency, "heartbeat": heartbeat}


def _build_health(snapshot: dict[str, Any]) -> dict[str, Any]:
    backend, _ = health_check._infer_db_backend()  # type: ignore[attr-defined]
    db_check = health_check.check_research_db(backend)
    risk_check = health_check.check_risk_engine()
    execution_check = health_check.check_execution()
    runner_check = health_check.check_runner()
    broker_status = snapshot.get("broker_status", {})
    return {
        "broker": _service_health(
            "Broker", broker_status.get("broker_connection", "UNKNOWN"),
            latency=broker_status.get("ping_ms", -1), heartbeat=broker_status.get("last_heartbeat", ""),
        ),
        "redis": _service_health("Redis", "N/A"),
        "database": _service_health("Database", db_check.get("status", "UNKNOWN")),
        "riskEngine": _service_health("Risk Engine", risk_check.get("status", "UNKNOWN")),
        "executionEngine": _service_health("Execution Engine", execution_check.get("status", "UNKNOWN")),
        "strategyEngine": _service_health("Strategy Engine", runner_check.get("status", "UNKNOWN")),
        "websocket": _service_health("WebSocket", "N/A"),
        "clockSync": _now_iso(),
    }


def _build_pairs(snapshot: dict[str, Any], chosen_symbol: str) -> dict[str, Any]:
    market_watch = snapshot.get("market_watch", {}).get("symbols", [])
    chart = snapshot.get("trading_chart", {})
    pipeline = {
        stage: {"status": "WAITING", "reason": "not instrumented by current strategy adapters", "timestamp": ""}
        for stage in _PIPELINE_STAGES
    }
    pairs: dict[str, Any] = {}
    for row in market_watch:
        symbol = str(row.get("symbol") or "")
        if not symbol:
            continue
        is_chart_symbol = symbol.upper() == str(chosen_symbol or "").upper()
        pairs[symbol] = {
            "symbol": symbol,
            "price": row.get("bid", 0.0),
            "trend": "UNKNOWN",
            "htfBias": "UNKNOWN",
            "spread": row.get("spread_pips", 0.0),
            "atr": 0.0,
            "swingHigh": 0.0,
            "swingLow": 0.0,
            "pipeline": pipeline,
            "activeObjects": [],
            "candles": chart.get("candles", []) if is_chart_symbol else [],
        }
    return pairs


def _build_history(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    trades = snapshot.get("trade_history", {}).get("trades", [])
    history = []
    for idx, row in enumerate(trades):
        pnl = row.get("profit")
        history.append({
            "id": f"trade-{idx}-{row.get('timestamp', '')}",
            "pair": row.get("symbol", ""),
            "type": "",
            "lots": 0.0,
            "entry": row.get("entry", 0.0),
            "exit": row.get("exit", 0.0),
            "sl": 0.0,
            "tp": 0.0,
            "pnl": pnl if pnl is not None else 0.0,
            "status": row.get("result", ""),
            "entryTime": "",
            "exitTime": row.get("timestamp", ""),
            "duration": row.get("duration", ""),
            "exitReason": row.get("notes", ""),
            "mae": None,
            "mfe": None,
            "latency": None,
            "slippage": row.get("slippage", 0.0),
            "commission": row.get("commission", 0.0),
            "realRr": None,
            "explanation": ["mae/mfe/latency/realRr not tracked by any current trade journal"],
        })
    return history


def _build_strategy_packages() -> list[dict[str, Any]]:
    packages = []
    for entry in strategy_service.list_strategies():
        rules = entry.get("rules") or {}
        risk_rules = rules.get("riskRules") or {}
        evidence = entry.get("evidence") or {}
        audit_log = entry.get("auditLog") or []
        packages.append({
            "id": entry.get("id", ""),
            "name": entry.get("name", entry.get("id", "")),
            "version": entry.get("version", ""),
            "signature": "",
            "symbols": [rules["symbol"]] if rules.get("symbol") else [],
            "broker_adapter": "vantage-metaapi",
            "risk_profile": risk_rules,
            "execution_rules": (rules.get("entryConditions") or []) + (rules.get("exitConditions") or []),
            "validation_score": evidence.get("validation_score", 0),
            "status": entry.get("status", ""),
            "lastSignalTime": "",
            "entryFrequency": 0,
            "latency": -1,
            "errorLogs": [str(item) for item in audit_log if isinstance(item, dict) and item.get("level") == "error"],
        })
    return packages


def _build_broker_connection(snapshot: dict[str, Any]) -> dict[str, Any]:
    broker_status = snapshot.get("broker_status", {})
    return {
        "status": broker_status.get("broker_connection", "UNKNOWN"),
        "latency": broker_status.get("ping_ms", -1),
        "orderSuccessRate": 0.0,
        "heartbeat": broker_status.get("last_heartbeat", ""),
        "apiCalls": 0,
    }


def build_live_state(*, chart_symbol: str | None = None, timeframe: str = "M15", candle_count: int = 120) -> dict[str, Any]:
    snapshot = live_dashboard_service.load_snapshot(chart_symbol=chart_symbol, timeframe=timeframe, candle_count=candle_count)
    chosen_symbol = snapshot.get("trading_chart", {}).get("symbol", chart_symbol or "")
    control = load_control_state()
    emergency = control.get("emergency_stop", {})

    try:
        journal_summary = TradeJournalDB().summary()
    except Exception:
        journal_summary = {"win_rate": 0.0, "avg_r": 0.0}

    market_watch = snapshot.get("market_watch", {}).get("symbols", [])
    avg_spread = (
        round(sum(row.get("spread_pips", 0.0) for row in market_watch) / len(market_watch), 2)
        if market_watch else 0.0
    )
    risk_dashboard = snapshot.get("risk_dashboard", {})
    orders = snapshot.get("orders", {})

    return {
        "pairs": _build_pairs(snapshot, chosen_symbol),
        "selectedPair": chosen_symbol,
        "health": _build_health(snapshot),
        "analytics": {
            "signalsQualified": 0,
            "signalsRejected": 0,
            "signalsExecuted": journal_summary.get("total", 0),
            "winRate": journal_summary.get("win_rate", 0.0),
            "avgRr": journal_summary.get("avg_r", 0.0),
            "avgSpread": avg_spread,
            "dailyRiskUsed": risk_dashboard.get("daily_risk", 0.0),
        },
        "rejections": [],
        "activeTrade": None,
        "history": _build_history(snapshot),
        "events": [],
        "isTradingPaused": bool(emergency.get("active", False)),
        "strategyPackages": _build_strategy_packages(),
        "activeDeployments": [],
        "riskControls": risk_dashboard.get("risk_limits", {}),
        "brokerConnection": _build_broker_connection(snapshot),
        "systemResources": {"cpu": 0.0, "ram": 0.0, "disk": 0.0},
        "failedOrders": [str(item.get("id", "")) for item in orders.get("rejected", [])],
        "retryQueue": [],
        "fetchedAt": snapshot.get("fetched_at", _now_iso()),
        "unavailable": _UNAVAILABLE_FIELDS,
    }
