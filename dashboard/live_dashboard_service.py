from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dashboard.control_state import load_control_state

ROOT = Path(__file__).resolve().parents[1]

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env", override=False)
except ImportError:  # pragma: no cover - optional dependency in minimal runtimes
    pass

from execution.mt5_connector import MT5Connector
from execution.trade_manager import TradeManager
from execution.vantage_demo_executor import VantageDemoExecutor

JOURNAL_PATHS = [
    ROOT / "logs" / "trades.jsonl",
    ROOT / "logs" / "adaptive_trades.jsonl",
    ROOT / "logs" / "strategy_demo_trades.jsonl",
    ROOT / "logs" / "st_a2_demo_trades.jsonl",
    ROOT / "logs" / "portfolio_demo_trades.jsonl",
]
BOT_STATE_PATH = ROOT / "logs" / "bot_state.json"
DEMO_CONFIG_PATH = ROOT / "config" / "demo.yaml"
DEFAULT_WATCHLIST = ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD"]
DEFAULT_TIMEFRAME = "M15"
DEFAULT_CANDLE_COUNT = 120
BROKER_TIMEOUT_S = 45
RPC_TIMEOUT_S = 20

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_yaml(path: Path) -> dict[str, Any]:
    if yaml is None or not path.exists():
        return {}
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_jsonl(paths: list[Path], limit: int = 500) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in paths:
        if not path.exists():
            continue
        for raw in path.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]:
            line = raw.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                rows.append(payload)
    rows.sort(key=lambda item: str(item.get("timestamp") or item.get("ts") or ""), reverse=True)
    return rows


def _parse_ts(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _watchlist_symbols() -> list[str]:
    raw = os.getenv("LIVE_DASHBOARD_SYMBOLS", "").strip()
    if raw:
        values = [item.strip().upper() for item in raw.split(",") if item.strip()]
        if values:
            return values

    demo_cfg = _read_yaml(DEMO_CONFIG_PATH)
    pairs = ((demo_cfg.get("trading") or {}).get("allowed_pairs") or [])
    values = [str(item).strip().upper() for item in pairs if str(item).strip()]
    return values or list(DEFAULT_WATCHLIST)


def _config_limits() -> dict[str, Any]:
    demo_cfg = _read_yaml(DEMO_CONFIG_PATH)
    risk = demo_cfg.get("risk", {}) if isinstance(demo_cfg.get("risk"), dict) else {}
    max_spread = ((demo_cfg.get("trading") or {}).get("max_spread_pips") or {})
    return {
        "daily_loss_limit_pct": _safe_float(risk.get("daily_loss_limit_pct"), 2.0),
        "weekly_loss_limit_pct": _safe_float(risk.get("weekly_loss_limit_pct"), 5.0),
        "monthly_loss_limit_pct": _safe_float(risk.get("monthly_loss_limit_pct"), 8.0),
        "max_consecutive_losses": _safe_int(risk.get("max_consecutive_losses"), 4),
        "max_open_positions": _safe_int(risk.get("max_open_positions"), 3),
        "max_trades_per_day": _safe_int(risk.get("max_trades_per_day"), 4),
        "max_lot_size": _safe_float(risk.get("max_lot_size"), 0.5),
        "max_spread_pips": max_spread if isinstance(max_spread, dict) else {},
    }


def _calc_closed_trade_pnl(record: dict[str, Any]) -> float | None:
    for key in ("profit", "realized_pnl", "pnl", "net_profit"):
        if record.get(key) not in (None, ""):
            return _safe_float(record.get(key))
    for key in ("result_r", "result_R", "r_multiple"):
        if record.get(key) not in (None, ""):
            return _safe_float(record.get(key))
    return None


def _closed_trade_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    closed: list[dict[str, Any]] = []
    for row in records:
        if row.get("event") == "POSITION_CLOSED":
            closed.append(row)
            continue
        if _calc_closed_trade_pnl(row) is not None:
            closed.append(row)
    return closed


def _sum_closed_pnl(records: list[dict[str, Any]], *, since: datetime | None = None) -> float:
    total = 0.0
    for row in records:
        if since is not None:
            ts = _parse_ts(row.get("timestamp") or row.get("ts"))
            if ts is None or ts < since:
                continue
        pnl = _calc_closed_trade_pnl(row)
        if pnl is not None:
            total += pnl
    return round(total, 2)


def _equity_curve(closed_records: list[dict[str, Any]], account_balance: float) -> list[dict[str, Any]]:
    if not closed_records:
        return []
    total_realized = _sum_closed_pnl(closed_records)
    baseline = account_balance - total_realized
    running = baseline
    points: list[dict[str, Any]] = []
    for row in sorted(
        closed_records,
        key=lambda item: str(item.get("timestamp") or item.get("ts") or ""),
    ):
        pnl = _calc_closed_trade_pnl(row)
        if pnl is None:
            continue
        running += pnl
        points.append(
            {
                "time": row.get("timestamp") or row.get("ts") or "",
                "value": round(running, 2),
            }
        )
    return points[-90:]


def _drawdown_percent(equity_points: list[dict[str, Any]], current_equity: float) -> float:
    values = [float(point.get("value", 0.0)) for point in equity_points if point.get("value") is not None]
    if current_equity:
        values.append(current_equity)
    if not values:
        return 0.0
    peak = max(values)
    if peak <= 0:
        return 0.0
    trough = min(values)
    dd = max(0.0, (peak - trough) / peak * 100.0)
    return round(dd, 2)


def _hold_time_label(open_time: Any) -> str:
    ts = _parse_ts(open_time)
    if ts is None:
        return ""
    delta = datetime.now(timezone.utc) - ts
    minutes = int(delta.total_seconds() // 60)
    hours, mins = divmod(max(0, minutes), 60)
    if hours:
        return f"{hours}h {mins}m"
    return f"{mins}m"


async def _fetch_broker_snapshot_async(symbols: list[str], chart_symbol: str, timeframe: str, candle_count: int) -> dict[str, Any]:
    token = os.getenv("METAAPI_TOKEN", "").strip()
    account_id = os.getenv("VANTAGE_DEMO_METAAPI_ID", "").strip()
    if not token or not account_id:
        return {
            "available": False,
            "status": "UNCONFIGURED",
            "detail": "METAAPI_TOKEN or VANTAGE_DEMO_METAAPI_ID missing",
            "account": {},
            "positions": [],
            "orders": [],
            "market_watch": [],
            "chart": {"symbol": chart_symbol, "timeframe": timeframe, "candles": []},
            "heartbeat": {"connected": False, "latency_ms": -1, "last_heartbeat": ""},
        }

    connector = MT5Connector(mode="demo")
    try:
        await asyncio.wait_for(connector.connect(), timeout=BROKER_TIMEOUT_S)
        executor = VantageDemoExecutor(connector)
        heartbeat = await asyncio.wait_for(connector.heartbeat(), timeout=RPC_TIMEOUT_S)
        account = await asyncio.wait_for(executor.get_account_info(), timeout=RPC_TIMEOUT_S)
        rpc = connector.connection
        raw_positions = await asyncio.wait_for(rpc.get_positions(), timeout=RPC_TIMEOUT_S)
        positions = []
        for item in raw_positions or []:
            position = {
                "id": item.get("id"),
                "symbol": item.get("symbol"),
                "direction": str(item.get("type", "")).replace("POSITION_TYPE_", "").lower(),
                "volume": _safe_float(item.get("volume")),
                "entry_price": _safe_float(item.get("openPrice")),
                "current_price": _safe_float(item.get("currentPrice")),
                "stop_loss": _safe_float(item.get("stopLoss")),
                "take_profit": _safe_float(item.get("takeProfit")),
                "unrealized_pnl": _safe_float(item.get("profit")),
                "strategy_name": item.get("comment") or item.get("clientId") or "strategy-demo",
                "status": "OPEN",
                "open_time": item.get("time"),
                "holding_time": _hold_time_label(item.get("time")),
                "magic": item.get("magic"),
            }
            positions.append(position)

        raw_orders = []
        if hasattr(rpc, "get_orders"):
            raw_orders = await asyncio.wait_for(rpc.get_orders(), timeout=RPC_TIMEOUT_S)
        orders = []
        for item in raw_orders or []:
            state = str(item.get("state") or item.get("status") or "PENDING")
            orders.append(
                {
                    "id": item.get("id") or item.get("clientId") or item.get("orderId"),
                    "symbol": item.get("symbol"),
                    "direction": str(item.get("type", "")).replace("ORDER_TYPE_", "").lower(),
                    "volume": _safe_float(item.get("volume")),
                    "entry_price": _safe_float(item.get("openPrice") or item.get("priceOpen") or item.get("price")),
                    "stop_loss": _safe_float(item.get("stopLoss")),
                    "take_profit": _safe_float(item.get("takeProfit")),
                    "status": state.upper(),
                    "created_at": item.get("time") or item.get("doneTime") or "",
                    "comment": item.get("comment") or "",
                }
            )

        market_watch = []
        for symbol in symbols:
            price = await asyncio.wait_for(executor.get_price(symbol), timeout=RPC_TIMEOUT_S)
            bid = _safe_float(price.get("bid"))
            ask = _safe_float(price.get("ask"))
            market_watch.append(
                {
                    "symbol": symbol,
                    "bid": bid,
                    "ask": ask,
                    "spread_pips": _safe_float(price.get("spread_pips")),
                    "time": price.get("time", ""),
                }
            )

        candles = await asyncio.wait_for(
            executor.get_candles(chart_symbol, timeframe, candle_count),
            timeout=RPC_TIMEOUT_S,
        )
        return {
            "available": True,
            "status": "CONNECTED" if heartbeat.get("connected") else "DEGRADED",
            "detail": "Vantage demo account connected",
            "account": {
                **account,
                "account_type": "demo",
                "server": os.getenv("VANTAGE_MT5_DEMO_SERVER", "").strip(),
                "account_id_masked": f"...{account_id[-6:]}" if account_id else "",
            },
            "positions": positions,
            "orders": orders,
            "market_watch": market_watch,
            "chart": {"symbol": chart_symbol, "timeframe": timeframe, "candles": candles},
            "heartbeat": heartbeat,
        }
    except Exception as exc:
        return {
            "available": False,
            "status": "DISCONNECTED",
            "detail": str(exc)[:240],
            "account": {},
            "positions": [],
            "orders": [],
            "market_watch": [],
            "chart": {"symbol": chart_symbol, "timeframe": timeframe, "candles": []},
            "heartbeat": {"connected": False, "latency_ms": -1, "last_heartbeat": ""},
        }
    finally:
        try:
            await connector.disconnect()
        except Exception:
            pass


def _fetch_broker_snapshot(symbols: list[str], chart_symbol: str, timeframe: str, candle_count: int) -> dict[str, Any]:
    try:
        return asyncio.run(_fetch_broker_snapshot_async(symbols, chart_symbol, timeframe, candle_count))
    except Exception as exc:
        return {
            "available": False,
            "status": "DISCONNECTED",
            "detail": f"broker snapshot failed: {exc}",
            "account": {},
            "positions": [],
            "orders": [],
            "market_watch": [],
            "chart": {"symbol": chart_symbol, "timeframe": timeframe, "candles": []},
            "heartbeat": {"connected": False, "latency_ms": -1, "last_heartbeat": ""},
        }


def _portfolio_payload(account: dict[str, Any], closed_records: list[dict[str, Any]], positions: list[dict[str, Any]]) -> dict[str, Any]:
    balance = _safe_float(account.get("balance"))
    equity = _safe_float(account.get("equity"), balance)
    curve = _equity_curve(closed_records, balance)
    symbol_totals: dict[str, float] = {}
    direction_exposure: dict[str, float] = {"long": 0.0, "short": 0.0}
    for pos in positions:
        symbol = str(pos.get("symbol") or "")
        volume = _safe_float(pos.get("volume"))
        symbol_totals[symbol] = round(symbol_totals.get(symbol, 0.0) + volume, 2)
        direction = str(pos.get("direction") or "").lower()
        if direction in direction_exposure:
            direction_exposure[direction] = round(direction_exposure[direction] + volume, 2)

    total_closed = len(closed_records)
    win_count = sum(1 for row in closed_records if (_calc_closed_trade_pnl(row) or 0.0) > 0)
    avg_pnl = round((_sum_closed_pnl(closed_records) / total_closed), 2) if total_closed else 0.0
    return {
        "summary": {
            "balance": balance,
            "equity": equity,
            "open_positions": len(positions),
            "closed_trades": total_closed,
            "win_rate_pct": round((win_count / total_closed) * 100.0, 1) if total_closed else 0.0,
            "average_trade_pnl": avg_pnl,
        },
        "equity_curve": curve,
        "exposure": direction_exposure,
        "asset_allocation": [{"symbol": symbol, "volume": volume} for symbol, volume in sorted(symbol_totals.items())],
        "symbol_distribution": [{"symbol": symbol, "count": sum(1 for pos in positions if pos.get("symbol") == symbol)} for symbol in sorted(symbol_totals)],
        "daily_statistics": {
            "pnl": _sum_closed_pnl(closed_records, since=datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)),
            "trades": sum(
                1
                for row in closed_records
                if (_parse_ts(row.get("timestamp") or row.get("ts")) or datetime.min.replace(tzinfo=timezone.utc))
                >= datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            ),
        },
        "monthly_statistics": {
            "pnl": _sum_closed_pnl(closed_records, since=datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)),
            "trades": sum(
                1
                for row in closed_records
                if (_parse_ts(row.get("timestamp") or row.get("ts")) or datetime.min.replace(tzinfo=timezone.utc))
                >= datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            ),
        },
        "performance_metrics": {
            "realized_pnl": _sum_closed_pnl(closed_records),
            "unrealized_pnl": round(sum(_safe_float(pos.get("unrealized_pnl")) for pos in positions), 2),
            "drawdown_pct": _drawdown_percent(curve, equity),
        },
    }


def _orders_payload(broker_orders: list[dict[str, Any]], records: list[dict[str, Any]]) -> dict[str, Any]:
    orders = list(broker_orders)
    for row in records:
        event = str(row.get("event") or "").upper()
        if event not in {"ORDER_SUBMITTED", "ORDER_FILLED", "ORDER_REJECTED"}:
            continue
        status = {
            "ORDER_SUBMITTED": "PENDING",
            "ORDER_FILLED": "FILLED",
            "ORDER_REJECTED": "REJECTED",
        }[event]
        orders.append(
            {
                "id": row.get("order_id") or row.get("id") or row.get("symbol"),
                "symbol": row.get("symbol", ""),
                "direction": row.get("direction") or row.get("side") or "",
                "volume": _safe_float(row.get("volume") or row.get("lots")),
                "entry_price": _safe_float(row.get("entry") or row.get("entry_price")),
                "stop_loss": _safe_float(row.get("sl")),
                "take_profit": _safe_float(row.get("tp")),
                "status": status,
                "created_at": row.get("timestamp") or row.get("ts") or "",
                "comment": row.get("reason") or "",
            }
        )
    deduped: dict[str, dict[str, Any]] = {}
    for item in orders:
        order_id = str(item.get("id") or "")
        if not order_id:
            continue
        deduped[order_id] = item
    all_orders = sorted(deduped.values(), key=lambda item: str(item.get("created_at") or ""), reverse=True)
    return {
        "pending": [item for item in all_orders if str(item.get("status")).upper() == "PENDING"],
        "filled": [item for item in all_orders if str(item.get("status")).upper() == "FILLED"],
        "cancelled": [item for item in all_orders if "CANCEL" in str(item.get("status")).upper()],
        "rejected": [item for item in all_orders if str(item.get("status")).upper() == "REJECTED"],
        "all": all_orders[:100],
    }


def _history_payload(closed_records: list[dict[str, Any]]) -> dict[str, Any]:
    trades = []
    for row in closed_records[:200]:
        trades.append(
            {
                "timestamp": row.get("timestamp") or row.get("ts") or "",
                "symbol": row.get("symbol", ""),
                "strategy": row.get("strategy") or row.get("strategy_name") or "",
                "entry": _safe_float(row.get("entry") or row.get("entry_price")),
                "exit": _safe_float(row.get("exit") or row.get("exit_price")),
                "duration": row.get("duration") or "",
                "profit": _calc_closed_trade_pnl(row),
                "commission": _safe_float(row.get("commission")),
                "swap": _safe_float(row.get("swap")),
                "slippage": _safe_float(row.get("slippage") or row.get("slippage_pips")),
                "notes": row.get("notes") or row.get("exit_reason") or "",
                "result": "WIN" if (_calc_closed_trade_pnl(row) or 0.0) > 0 else "LOSS",
            }
        )
    return {"trades": trades}


def _execution_payload(records: list[dict[str, Any]], broker_status: str) -> dict[str, Any]:
    queue = []
    for row in records:
        event = str(row.get("event") or "").upper()
        if event not in {"SIGNAL_CREATED", "ORDER_SUBMITTED", "ORDER_FILLED", "ORDER_REJECTED", "ERROR"}:
            continue
        queue.append(
            {
                "time": row.get("timestamp") or row.get("ts") or "",
                "symbol": row.get("symbol", ""),
                "event": event,
                "status": "FAILED" if event in {"ORDER_REJECTED", "ERROR"} else "OK",
                "broker_response": row.get("reason") or row.get("error") or "",
                "retry_count": _safe_int(row.get("retry_count")),
                "processing_time_ms": _safe_float(row.get("processing_time_ms")),
            }
        )
    latest = queue[:25]
    latencies = [item["processing_time_ms"] for item in latest if item["processing_time_ms"] > 0]
    average_latency = round(sum(latencies) / len(latencies), 1) if latencies else 0.0
    return {
        "current_execution_queue": latest,
        "execution_latency_ms": average_latency,
        "order_status": latest[0]["status"] if latest else "IDLE",
        "fill_status": next((item["status"] for item in latest if item["event"] == "ORDER_FILLED"), "IDLE"),
        "broker_response": latest[0]["broker_response"] if latest else "",
        "retry_count": max((item["retry_count"] for item in latest), default=0),
        "processing_time_ms": latest[0]["processing_time_ms"] if latest else 0.0,
        "broker_status": broker_status,
    }


def _risk_payload(
    account: dict[str, Any],
    positions: list[dict[str, Any]],
    closed_records: list[dict[str, Any]],
    limits: dict[str, Any],
    bot_state: dict[str, Any],
    emergency_state: dict[str, Any],
) -> dict[str, Any]:
    balance = _safe_float(account.get("balance"), 0.0)
    equity = _safe_float(account.get("equity"), balance)
    margin = _safe_float(account.get("margin"))
    free_margin = _safe_float(account.get("free_margin"))
    open_risk = round(sum(abs(_safe_float(pos.get("unrealized_pnl"))) for pos in positions if _safe_float(pos.get("unrealized_pnl")) < 0), 2)
    current_drawdown = _drawdown_percent(_equity_curve(closed_records, balance), equity)
    daily_pnl = _sum_closed_pnl(closed_records, since=datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0))
    daily_limit_amount = round(balance * (limits["daily_loss_limit_pct"] / 100.0), 2) if balance else 0.0
    exposure = round(sum(_safe_float(pos.get("volume")) for pos in positions), 2)
    warnings = []
    if emergency_state.get("active"):
        warnings.append({"level": "critical", "message": emergency_state.get("reason") or "Emergency stop active"})
    if daily_limit_amount and daily_pnl < 0 and abs(daily_pnl) >= daily_limit_amount * 0.8:
        warnings.append({"level": "warning", "message": "Daily loss is near configured limit"})
    if bot_state.get("halted"):
        warnings.append({"level": "critical", "message": bot_state.get("halt_reason") or "Risk manager halted"})
    return {
        "daily_risk": round(abs(min(daily_pnl, 0.0)), 2),
        "open_risk": open_risk,
        "exposure": exposure,
        "current_drawdown_pct": current_drawdown,
        "maximum_drawdown_pct": current_drawdown,
        "position_size": max((_safe_float(pos.get("volume")) for pos in positions), default=0.0),
        "margin_usage_pct": round((margin / equity) * 100.0, 2) if equity else 0.0,
        "risk_limits": limits,
        "daily_loss_limit": daily_limit_amount,
        "consecutive_losses": _safe_int(bot_state.get("consecutive_losses")),
        "free_margin": free_margin,
        "warnings": warnings,
    }


def _broker_payload(
    broker: dict[str, Any],
    market_watch: list[dict[str, Any]],
    overview_status: str,
    execution_status: dict[str, Any],
) -> dict[str, Any]:
    heartbeat = broker.get("heartbeat", {}) if isinstance(broker.get("heartbeat"), dict) else {}
    account = broker.get("account", {}) if isinstance(broker.get("account"), dict) else {}
    average_spread = round(
        sum(_safe_float(item.get("spread_pips")) for item in market_watch) / len(market_watch),
        2,
    ) if market_watch else 0.0
    return {
        "broker_connection": broker.get("status", "UNKNOWN"),
        "mt5_status": "CONNECTED" if heartbeat.get("connected") else "DISCONNECTED",
        "metaapi_status": broker.get("status", "UNKNOWN"),
        "ping_ms": heartbeat.get("latency_ms", -1),
        "server_time": market_watch[0].get("time", "") if market_watch else "",
        "account_type": account.get("account_type", "demo"),
        "market_open_status": overview_status,
        "spread": average_spread,
        "connection_quality": "GOOD" if heartbeat.get("connected") and _safe_float(heartbeat.get("latency_ms"), 1000) < 500 else "DEGRADED",
        "server": account.get("server", ""),
        "broker_response": execution_status.get("broker_response", ""),
        "last_heartbeat": heartbeat.get("last_heartbeat", ""),
    }


def _overview_payload(
    account: dict[str, Any],
    positions: list[dict[str, Any]],
    orders: dict[str, Any],
    closed_records: list[dict[str, Any]],
    broker: dict[str, Any],
    risk: dict[str, Any],
) -> dict[str, Any]:
    balance = _safe_float(account.get("balance"))
    equity = _safe_float(account.get("equity"), balance)
    margin = _safe_float(account.get("margin"))
    free_margin = _safe_float(account.get("free_margin"))
    unrealized = round(sum(_safe_float(pos.get("unrealized_pnl")) for pos in positions), 2)
    daily_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = daily_start.replace(day=max(1, daily_start.day - daily_start.weekday()))
    month_start = daily_start.replace(day=1)
    return {
        "account_balance": balance,
        "equity": equity,
        "unrealized_pnl": unrealized,
        "realized_pnl": _sum_closed_pnl(closed_records),
        "daily_pnl": _sum_closed_pnl(closed_records, since=daily_start),
        "weekly_pnl": _sum_closed_pnl(closed_records, since=week_start),
        "monthly_pnl": _sum_closed_pnl(closed_records, since=month_start),
        "margin": margin,
        "free_margin": free_margin,
        "margin_level_pct": round((equity / margin) * 100.0, 2) if margin else 0.0,
        "drawdown_pct": risk.get("current_drawdown_pct", 0.0),
        "todays_risk": risk.get("daily_risk", 0.0),
        "open_positions": len(positions),
        "pending_orders": len(orders.get("pending", [])),
        "broker_status": broker.get("status", "UNKNOWN"),
        "market_status": "OPEN" if broker.get("available") else "DEGRADED",
        "connection_health": broker.get("status", "UNKNOWN"),
        "last_update_time": _now_iso(),
    }


def load_snapshot(*, chart_symbol: str | None = None, timeframe: str = DEFAULT_TIMEFRAME, candle_count: int = DEFAULT_CANDLE_COUNT) -> dict[str, Any]:
    symbols = _watchlist_symbols()
    chosen_symbol = (chart_symbol or symbols[0]).upper()
    records = _read_jsonl(JOURNAL_PATHS)
    closed_records = _closed_trade_records(records)
    broker = _fetch_broker_snapshot(symbols, chosen_symbol, timeframe, candle_count)
    account = broker.get("account", {}) if isinstance(broker.get("account"), dict) else {}
    positions = broker.get("positions", []) if isinstance(broker.get("positions"), list) else []
    orders = _orders_payload(broker.get("orders", []) if isinstance(broker.get("orders"), list) else [], records)
    history = _history_payload(closed_records)
    limits = _config_limits()
    bot_state = _read_json(BOT_STATE_PATH)
    control = load_control_state()
    execution = _execution_payload(records, str(broker.get("status", "UNKNOWN")))
    risk = _risk_payload(account, positions, closed_records, limits, bot_state, control.get("emergency_stop", {}))
    market_watch = broker.get("market_watch", []) if isinstance(broker.get("market_watch"), list) else []
    portfolio = _portfolio_payload(account, closed_records, positions)
    broker_status = _broker_payload(broker, market_watch, "OPEN" if broker.get("available") else "DEGRADED", execution)
    overview = _overview_payload(account, positions, orders, closed_records, broker, risk)
    return {
        "overview": overview,
        "portfolio": portfolio,
        "positions": {"items": positions, "count": len(positions)},
        "orders": orders,
        "trade_history": history,
        "execution_monitor": execution,
        "risk_dashboard": risk,
        "broker_status": broker_status,
        "market_watch": {"symbols": market_watch, "watchlist": symbols},
        "trading_chart": broker.get("chart", {"symbol": chosen_symbol, "timeframe": timeframe, "candles": []}),
        "system": {
            "trading_mode": "demo",
            "demo_only": _env_bool("DEMO_ONLY", True),
            "live_trading_enabled": _env_bool("LIVE_TRADING", False),
            "vantage_demo_configured": bool(os.getenv("VANTAGE_DEMO_METAAPI_ID", "").strip()),
            "metaapi_configured": bool(os.getenv("METAAPI_TOKEN", "").strip()),
            "emergency_stop": control.get("emergency_stop", {}),
        },
        "fetched_at": _now_iso(),
    }


async def _close_position_async(position_id: str) -> dict[str, Any]:
    connector = MT5Connector(mode="demo")
    try:
        await asyncio.wait_for(connector.connect(), timeout=BROKER_TIMEOUT_S)
        executor = VantageDemoExecutor(connector)
        manager = TradeManager(executor)
        closed = await asyncio.wait_for(manager.close_position(position_id), timeout=RPC_TIMEOUT_S)
        return {"ok": bool(closed), "position_id": position_id, "simulated": executor.demo_only}
    finally:
        try:
            await connector.disconnect()
        except Exception:
            pass


def close_position(position_id: str) -> dict[str, Any]:
    try:
        return asyncio.run(_close_position_async(position_id))
    except Exception as exc:
        return {"ok": False, "position_id": position_id, "error": str(exc), "simulated": False}


async def _modify_position_async(position_id: str, stop_loss: float, take_profit: float) -> dict[str, Any]:
    connector = MT5Connector(mode="demo")
    try:
        await asyncio.wait_for(connector.connect(), timeout=BROKER_TIMEOUT_S)
        executor = VantageDemoExecutor(connector)
        manager = TradeManager(executor)
        updated = await asyncio.wait_for(manager.modify_sl_tp(position_id, stop_loss, take_profit), timeout=RPC_TIMEOUT_S)
        return {
            "ok": bool(updated),
            "position_id": position_id,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "simulated": executor.demo_only,
        }
    finally:
        try:
            await connector.disconnect()
        except Exception:
            pass


def modify_position(position_id: str, stop_loss: float, take_profit: float) -> dict[str, Any]:
    try:
        return asyncio.run(_modify_position_async(position_id, stop_loss, take_profit))
    except Exception as exc:
        return {
            "ok": False,
            "position_id": position_id,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "error": str(exc),
            "simulated": False,
        }


async def _cancel_order_async(order_id: str) -> dict[str, Any]:
    connector = MT5Connector(mode="demo")
    try:
        await asyncio.wait_for(connector.connect(), timeout=BROKER_TIMEOUT_S)
        executor = VantageDemoExecutor(connector)
        if executor.demo_only:
            return {"ok": True, "order_id": order_id, "simulated": True}
        rpc = connector.connection
        for method_name in ("cancel_order", "remove_order"):
            method = getattr(rpc, method_name, None)
            if method is None:
                continue
            await asyncio.wait_for(method(order_id), timeout=RPC_TIMEOUT_S)
            return {"ok": True, "order_id": order_id, "simulated": False}
        return {"ok": False, "order_id": order_id, "error": "Broker RPC does not expose cancel_order/remove_order"}
    finally:
        try:
            await connector.disconnect()
        except Exception:
            pass


def cancel_order(order_id: str) -> dict[str, Any]:
    try:
        return asyncio.run(_cancel_order_async(order_id))
    except Exception as exc:
        return {"ok": False, "order_id": order_id, "error": str(exc), "simulated": False}
