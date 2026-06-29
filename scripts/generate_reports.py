#!/usr/bin/env python3
"""Generate operator-facing Markdown reports for the trading platform.

This script is intentionally read-only with respect to trading/runtime state.
It reads existing configs, logs, journals, and validation artifacts, then
writes Markdown reports into `reports/`.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

try:
    import yaml
except Exception:  # pragma: no cover - optional dependency in some runtimes
    yaml = None

ROOT = Path(__file__).resolve().parents[1]
UTC = timezone.utc

SUPPORTED_TYPES = (
    "daily",
    "weekly",
    "monthly",
    "strategy",
    "risk",
    "execution",
    "system-health",
    "database-health",
    "incident",
    "live-readiness",
    "all",
)

REPORT_DIRS = {
    "daily": "daily",
    "weekly": "weekly",
    "monthly": "monthly",
    "strategy": "strategy",
    "risk": "risk",
    "execution": "execution",
    "system-health": "system_health",
    "database-health": "system_health",
    "incident": "incidents",
    "live-readiness": "live_readiness",
}

TRADE_EVENT_LOG = ROOT / "logs" / "trades.jsonl"
BOT_LOG = ROOT / "logs" / "bot.log"
RUNNER_LOGS = [
    ROOT / "logs" / "strategy_demo.log",
    ROOT / "logs" / "st_a2_demo.log",
    ROOT / "logs" / "st_a2_runner.log",
]
RUNNER_LOG = RUNNER_LOGS[-1]
DEMO_JOURNALS = [
    ROOT / "logs" / "strategy_demo_trades.jsonl",
    ROOT / "logs" / "st_a2_demo_trades.jsonl",
    ROOT / "logs" / "adaptive_trades.jsonl",
    ROOT / "logs" / "portfolio_demo_trades.jsonl",
]
TRADE_DB = ROOT / "data" / "trade_journal.db"
BOT_STATE = ROOT / "logs" / "bot_state.json"
EXECUTION_DAILY = ROOT / "logs" / "execution_summary_daily.json"
EXECUTION_WEEKLY = ROOT / "logs" / "execution_summary_weekly.json"
CATALOG = ROOT / "config" / "strategy_catalog.yaml"
DEMO_CONFIG = ROOT / "config" / "demo.yaml"
VALIDATION_CONFIG = ROOT / "config" / "validation.yaml"
PROJECT_STATUS = ROOT / "docs" / "PROJECT_STATUS.md"

sys.path.insert(0, str(ROOT))
import scripts.health_check as health_check  # noqa: E402


@dataclass
class ReportArtifact:
    report_type: str
    path: Path


def _now() -> datetime:
    return datetime.now(UTC)


def _safe_read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def _safe_load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _safe_load_yaml(path: Path) -> dict[str, Any]:
    if yaml is None or not path.exists():
        return {}
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def ensure_report_dirs(root: Path = ROOT) -> dict[str, Path]:
    report_root = root / "reports"
    created: dict[str, Path] = {}
    for key, rel in REPORT_DIRS.items():
        path = report_root / rel
        path.mkdir(parents=True, exist_ok=True)
        created[key] = path
    return created


def _report_path(report_type: str, ts: datetime, root: Path = ROOT) -> Path:
    dirname = ensure_report_dirs(root)[report_type]
    stem = report_type.replace("-", "_")
    if report_type in {"daily", "weekly", "monthly"}:
        suffix = ts.strftime("%Y-%m-%d")
    else:
        suffix = ts.strftime("%Y-%m-%d_%H%M%S")
    return dirname / f"{stem}_report_{suffix}.md"


def _jsonl_records(paths: list[Path]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in paths:
        if not path.exists():
            continue
        for line in _safe_read_text(path).splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                records.append(item)
    return records


def _read_log_tails(paths: list[Path], limit: int) -> list[str]:
    lines: list[str] = []
    for path in paths:
        lines.extend(_read_log_tail(path, limit))
    return lines


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _records_since(records: list[dict[str, Any]], since: datetime) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in records:
        dt = _parse_dt(item.get("timestamp") or item.get("ts"))
        if dt is not None and dt >= since:
            out.append(item)
    return out


def _trade_db_rows(path: Path = TRADE_DB, limit: int = 5000) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        conn = sqlite3.connect(str(path))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM trades ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        ).fetchall()
    except sqlite3.Error:
        return []
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return [dict(row) for row in rows]


def _trade_db_summary(path: Path = TRADE_DB) -> dict[str, Any]:
    rows = _trade_db_rows(path)
    closed = [r for r in rows if r.get("status") == "CLOSED"]
    wins = [r for r in closed if (r.get("r_multiple") or 0) > 0]
    losses = [r for r in closed if (r.get("r_multiple") or 0) < 0]
    gross_win = sum(float(r.get("r_multiple") or 0.0) for r in wins)
    gross_loss = abs(sum(float(r.get("r_multiple") or 0.0) for r in losses))
    return {
        "total": len(rows),
        "open": sum(1 for r in rows if r.get("status") == "OPEN"),
        "closed": len(closed),
        "blocked": sum(1 for r in rows if r.get("status") == "BLOCKED"),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate_pct": round(len(wins) / len(closed) * 100, 1) if closed else 0.0,
        "avg_r": round(sum(float(r.get("r_multiple") or 0.0) for r in closed) / len(closed), 3) if closed else 0.0,
        "profit_factor": round(gross_win / gross_loss, 3) if gross_loss > 0 else 0.0,
        "gross_win_r": round(gross_win, 3),
        "gross_loss_r": round(gross_loss, 3),
    }


def _load_catalog() -> dict[str, Any]:
    return _safe_load_yaml(CATALOG)


def _current_strategy_manifest() -> tuple[str, dict[str, Any]]:
    catalog = _load_catalog()
    current = str(catalog.get("current_strategy") or "ST-A2")
    manifest = (catalog.get("strategies") or {}).get(current) or {}
    return current, manifest


def _system_mode() -> str:
    env_mode = os.environ.get("TRADING_MODE", "").strip().lower()
    if env_mode in {"research", "demo", "live", "shadow"}:
        return "research" if env_mode == "shadow" else env_mode
    demo_cfg = _safe_load_yaml(DEMO_CONFIG)
    cfg_mode = str(demo_cfg.get("execution", {}).get("mode", "")).strip().lower()
    if cfg_mode in {"research", "demo", "live", "shadow"}:
        return "research" if cfg_mode == "shadow" else cfg_mode
    _, manifest = _current_strategy_manifest()
    status = str(manifest.get("status", "")).lower()
    return "demo" if status in {"demo", "walk_forward", "shadow"} else "research"


def _bot_state() -> dict[str, Any]:
    return _safe_load_json(BOT_STATE)


def _read_log_tail(path: Path, lines: int = 400) -> list[str]:
    text = _safe_read_text(path)
    if not text:
        return []
    return text.splitlines()[-lines:]


def _recent_log_scan() -> dict[str, Any]:
    lines = _read_log_tail(BOT_LOG, 600) + _read_log_tails(RUNNER_LOGS, 400)
    errors = [line for line in lines if "ERROR" in line]
    critical = [line for line in lines if "CRITICAL" in line or "FATAL" in line]
    disconnect = any("DISCONNECTED" in line or "RPC timeout" in line for line in lines)
    reconnect = any("reconnect" in line.lower() for line in lines)
    last_success = next((line for line in reversed(lines) if "connected" in line.lower() or "filled" in line.lower()), "")
    return {
        "error_count": len(errors),
        "critical_count": len(critical),
        "critical_lines": critical[-5:],
        "disconnect_seen": disconnect,
        "reconnect_seen": reconnect,
        "last_success_line": last_success[-180:],
    }


def _health_snapshot() -> dict[str, Any]:
    db_backend, _ = health_check._infer_db_backend()  # type: ignore[attr-defined]
    db_status = health_check.check_research_db(db_backend)
    runner = health_check.check_runner()
    risk = health_check.check_risk_engine()
    recovery = health_check.check_recovery()
    execution = health_check.check_execution()
    logs = _recent_log_scan()
    broker_status = {
        "status": "WARN" if logs["disconnect_seen"] else "UNKNOWN",
        "detail": "recent disconnects seen in logs" if logs["disconnect_seen"] else "no live probe performed by report generator",
    }
    if execution["status"] in {"SHADOW", "READY"} and not logs["disconnect_seen"]:
        broker_status = {"status": "INFO", "detail": "execution mode configured; broker/API not actively probed"}
    return {
        "runner": runner,
        "database": db_status,
        "risk": risk,
        "recovery": recovery,
        "execution": execution,
        "broker": broker_status,
        "logs": logs,
    }


def _trade_records_window(days: int) -> dict[str, Any]:
    since = _now() - timedelta(days=days)
    journal_records = _records_since(_jsonl_records(DEMO_JOURNALS), since)
    event_records = _records_since(_jsonl_records([TRADE_EVENT_LOG]), since)
    db_rows = [
        row for row in _trade_db_rows()
        if (_parse_dt(row.get("timestamp")) or datetime.min.replace(tzinfo=UTC)) >= since
    ]
    return {
        "journal_records": journal_records,
        "event_records": event_records,
        "db_rows": db_rows,
    }


def _journal_metrics(days: int) -> dict[str, Any]:
    window = _trade_records_window(days)
    records = window["journal_records"]
    opens = [r for r in records if r.get("record_type") == "open"]
    closes = [r for r in records if r.get("record_type") == "close" and r.get("result_R") is not None]
    wins = [r for r in closes if float(r.get("result_R") or 0.0) > 0]
    losses = [r for r in closes if float(r.get("result_R") or 0.0) < 0]
    gross_win = sum(float(r.get("result_R") or 0.0) for r in wins)
    gross_loss = abs(sum(float(r.get("result_R") or 0.0) for r in losses))

    r_values = [float(r.get("result_R") or 0.0) for r in closes]
    cumulative = 0.0
    peak = 0.0
    max_dd = 0.0
    consec_losses = 0
    max_consec = 0
    for r in r_values:
        cumulative += r
        peak = max(peak, cumulative)
        max_dd = max(max_dd, peak - cumulative)
        if r < 0:
            consec_losses += 1
            max_consec = max(max_consec, consec_losses)
        else:
            consec_losses = 0

    open_sessions = Counter(str(r.get("session") or "unknown") for r in opens)
    close_by_symbol = Counter(str(r.get("symbol") or "unknown") for r in closes)
    return {
        "trades_opened": len(opens),
        "trades_closed": len(closes),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate_pct": round(len(wins) / len(closes) * 100, 1) if closes else 0.0,
        "net_r": round(sum(r_values), 3),
        "profit_factor": round(gross_win / gross_loss, 3) if gross_loss > 0 else 0.0,
        "max_drawdown_r": round(max_dd, 3),
        "consecutive_losses": max_consec,
        "avg_r": round(sum(r_values) / len(r_values), 3) if r_values else 0.0,
        "sessions": dict(open_sessions),
        "pairs": dict(close_by_symbol),
        "window": window,
    }


def _event_metrics(days: int) -> dict[str, Any]:
    records = _trade_records_window(days)["event_records"]
    counter = Counter(str(r.get("event") or "UNKNOWN") for r in records)
    rejects = [r for r in records if r.get("event") == "ORDER_REJECTED"]
    reasons = Counter(str(r.get("reason") or "UNKNOWN").split(":", 1)[0] for r in rejects)
    return {
        "signals": counter.get("SIGNAL_CREATED", 0),
        "submitted": counter.get("ORDER_SUBMITTED", 0),
        "filled": counter.get("ORDER_FILLED", 0),
        "closed": counter.get("POSITION_CLOSED", 0),
        "rejected": counter.get("ORDER_REJECTED", 0),
        "errors": counter.get("ERROR", 0),
        "reject_reasons": dict(reasons),
        "fill_rate": round(counter.get("ORDER_FILLED", 0) / counter.get("ORDER_SUBMITTED", 1), 3) if counter.get("ORDER_SUBMITTED", 0) else 0.0,
    }


def _strategy_metrics(days: int = 30) -> dict[str, Any]:
    current, manifest = _current_strategy_manifest()
    records = _journal_metrics(days)
    closes = records["window"]["journal_records"]
    strategy_closes = [r for r in closes if r.get("record_type") == "close"]
    open_records = [r for r in records["window"]["journal_records"] if r.get("record_type") == "open"]
    session = Counter(str(r.get("session") or "unknown") for r in open_records).most_common(1)
    best_symbol = max(records["pairs"].items(), key=lambda item: item[1])[0] if records["pairs"] else "n/a"
    worst_symbol = min(records["pairs"].items(), key=lambda item: item[1])[0] if records["pairs"] else "n/a"
    status = str(manifest.get("status", "unknown")).upper()
    if manifest.get("last_svos_status") == "FAIL":
        recommendation = "CONTINUE DEMO"
        robustness = "REVIEW_REQUIRED"
    elif records["trades_closed"] >= 20 and records["profit_factor"] >= 1.1:
        recommendation = "PROMOTE"
        robustness = "PASS"
    elif records["trades_closed"] == 0:
        recommendation = "NEED MORE DATA"
        robustness = "INSUFFICIENT_DATA"
    elif records["profit_factor"] < 1.0:
        recommendation = "RETIRE"
        robustness = "FAIL"
    else:
        recommendation = "CONTINUE DEMO"
        robustness = f"{status}_MONITOR"
    return {
        "strategy_name": current,
        "pair": ", ".join(manifest.get("symbols", []) or ["n/a"]),
        "session": session[0][0] if session else "mixed",
        "number_of_trades": records["trades_closed"],
        "win_rate_pct": records["win_rate_pct"],
        "gross_pf": records["profit_factor"],
        "net_pf": records["profit_factor"],
        "expectancy": records["avg_r"],
        "max_drawdown_r": records["max_drawdown_r"],
        "best_setup": best_symbol,
        "worst_setup": worst_symbol,
        "robustness_status": robustness,
        "recommendation": recommendation,
        "manifest": manifest,
        "strategy_closes": strategy_closes,
    }


def _risk_metrics(days: int = 1) -> dict[str, Any]:
    state = _bot_state()
    records = _journal_metrics(max(days, 7))
    limits = {
        "per_trade_risk_pct": 0.25,
        "daily_loss_limit_pct": 1.5,
        "max_consecutive_losses": 3,
    }
    breaches: list[str] = []
    if state.get("halted"):
        breaches.append(str(state.get("halt_reason") or "HALTED"))
    if records["consecutive_losses"] >= limits["max_consecutive_losses"]:
        breaches.append("CONSECUTIVE_LOSS_LIMIT")
    if state.get("daily_loss_pct", 0.0) >= 0.015:
        breaches.append("DAILY_LOSS_LIMIT")
    recommendation = "PAUSE" if breaches else "CONTINUE"
    return {
        "current_exposure": int(state.get("open_positions", 0)),
        "daily_risk_used_pct": round(float(state.get("daily_loss_pct", 0.0)) * 100, 3),
        "per_trade_risk_pct": limits["per_trade_risk_pct"],
        "max_drawdown_r": records["max_drawdown_r"],
        "consecutive_losses": int(state.get("consecutive_losses", records["consecutive_losses"])),
        "emergency_stop_status": "ENGAGED" if state.get("halted") else "CLEAR",
        "risk_breaches": breaches or ["NONE"],
        "recommendation": recommendation,
    }


def _execution_metrics() -> dict[str, Any]:
    summary = _safe_load_json(EXECUTION_DAILY) or _safe_load_json(EXECUTION_WEEKLY)
    events = _event_metrics(7)
    if summary:
        failures = summary.get("execution_failures", {})
        lat_a = summary.get("signal_to_order_latency", {})
        lat_b = summary.get("order_to_fill_latency", {})
        return {
            "source": "execution_summary",
            "signal_to_order_avg_ms": lat_a.get("avg_ms"),
            "order_to_fill_avg_ms": lat_b.get("avg_ms"),
            "fill_rate": failures.get("fill_rate"),
            "orders_rejected": failures.get("orders_rejected"),
            "orders_filled": failures.get("orders_filled"),
            "reject_reasons": failures.get("by_reason", {}),
            "slippage": summary.get("slippage_distribution", {}),
            "reconnects": summary.get("reconnect_during_trade", {}),
        }
    return {
        "source": "event_log",
        "signal_to_order_avg_ms": None,
        "order_to_fill_avg_ms": None,
        "fill_rate": events["fill_rate"],
        "orders_rejected": events["rejected"],
        "orders_filled": events["filled"],
        "reject_reasons": events["reject_reasons"],
        "slippage": {},
        "reconnects": {},
    }


def _live_readiness_metrics() -> dict[str, Any]:
    current, manifest = _current_strategy_manifest()
    health = _health_snapshot()
    strategy = _strategy_metrics(30)
    incidents = _incident_metrics(30)
    validation = _safe_load_yaml(VALIDATION_CONFIG)
    gate_ok = bool(manifest.get("approved")) and bool(manifest.get("last_svos_verification_ready"))
    execution_ready = health["execution"]["status"] in {"READY", "SHADOW"}
    database_stable = health["database"]["status"] in {"PASS", "SKIP"}
    risk_ok = health["risk"]["status"] == "PASS"
    governance_ok = manifest.get("deployment_target") in {"execution", "shadow", "demo", "live"}
    if not gate_ok:
        verdict = "NOT_READY"
    elif execution_ready and database_stable and risk_ok and strategy["recommendation"] in {"PROMOTE", "CONTINUE DEMO"}:
        verdict = "DEMO_READY"
    else:
        verdict = "NOT_READY"
    if verdict == "DEMO_READY" and manifest.get("status") == "live":
        verdict = "LIVE_READY"
    return {
        "strategy": current,
        "validation_gate_status": "PASS" if gate_ok else "FAIL",
        "paper_trading_result": strategy["recommendation"],
        "execution_stability": health["execution"]["status"],
        "database_stability": health["database"]["status"],
        "risk_firewall_status": health["risk"]["status"],
        "governance_status": "PASS" if governance_ok else "FAIL",
        "emergency_stop_test": health["recovery"]["status"],
        "incident_count": incidents["incident_count"],
        "final_verdict": verdict,
        "validation_config": validation,
    }


def _incident_metrics(days: int = 7) -> dict[str, Any]:
    since = _now() - timedelta(days=days)
    lines = _read_log_tail(BOT_LOG, 1000) + _read_log_tails(RUNNER_LOGS, 1000)
    filtered = []
    for line in lines:
        if not any(token in line for token in ("ERROR", "CRITICAL", "WARN", "disconnect", "Disconnect")):
            continue
        filtered.append(line)
    recent = filtered[-20:]
    critical = [line for line in recent if "CRITICAL" in line or "FATAL" in line]
    return {
        "incident_count": len(recent),
        "critical_count": len(critical),
        "recent_lines": recent,
        "since": since.isoformat(),
    }


def _final_recommendation(daily: dict[str, Any], risk: dict[str, Any], health: dict[str, Any]) -> str:
    if risk["risk_breaches"] != ["NONE"] or health["logs"]["critical_count"] > 0:
        return "PAUSE"
    if health["database"]["status"] == "FAIL" or health["runner"]["status"] == "FAIL":
        return "REVIEW"
    return "CONTINUE"


def _markdown_header(title: str, generated_at: datetime) -> list[str]:
    return [
        f"# {title}",
        "",
        f"_Generated: {generated_at.isoformat()}_",
        "",
    ]


def build_daily_report(ts: datetime) -> str:
    daily = _journal_metrics(1)
    events = _event_metrics(1)
    risk = _risk_metrics(1)
    health = _health_snapshot()
    final = _final_recommendation(daily, risk, health)
    lines = _markdown_header("Daily Trading Report", ts)
    lines += [
        "## Summary",
        "",
        f"- Date: `{ts.date().isoformat()}`",
        f"- System mode: `{_system_mode()}`",
        f"- Trades opened: `{daily['trades_opened']}`",
        f"- Trades closed: `{daily['trades_closed']}`",
        f"- Win rate: `{daily['win_rate_pct']}%`",
        f"- Net R: `{daily['net_r']}`",
        f"- Profit factor: `{daily['profit_factor']}`",
        f"- Max drawdown: `{daily['max_drawdown_r']}R`",
        f"- Rejected signals: `{events['rejected']}`",
        f"- Risk limit status: `{risk['emergency_stop_status']}`",
        f"- Database status: `{health['database']['status']}`",
        f"- Broker status: `{health['broker']['detail']}`",
        f"- Critical incidents: `{health['logs']['critical_count']}`",
        f"- Final recommendation: `{final}`",
        "",
        "## Operator Notes",
        "",
        f"- Signal count observed in event log: `{events['signals']}`",
        f"- Recovery status: `{health['recovery']['status']}`",
        f"- Last success line: `{health['logs']['last_success_line'] or 'n/a'}`",
        "",
    ]
    return "\n".join(lines).rstrip() + "\n"


def build_weekly_report(ts: datetime) -> str:
    weekly = _journal_metrics(7)
    events = _event_metrics(7)
    incidents = _incident_metrics(7)
    lines = _markdown_header("Weekly Review Report", ts)
    lines += [
        "## Weekly Summary",
        "",
        f"- Review window: `{(_now() - timedelta(days=7)).date().isoformat()} -> {ts.date().isoformat()}`",
        f"- Trades closed: `{weekly['trades_closed']}`",
        f"- Win rate: `{weekly['win_rate_pct']}%`",
        f"- Net R: `{weekly['net_r']}`",
        f"- Profit factor: `{weekly['profit_factor']}`",
        f"- Max drawdown: `{weekly['max_drawdown_r']}R`",
        f"- Signals: `{events['signals']}`",
        f"- Rejections: `{events['rejected']}`",
        f"- Incidents logged: `{incidents['incident_count']}`",
        "",
        "## Owner Review Actions",
        "",
        "- Confirm whether any rejected signals were expected risk/filter behavior.",
        "- Compare strategy recommendation to current registry stage before promotion.",
        "- Check incident lines and decide whether any need a formal incident report.",
        "",
    ]
    return "\n".join(lines).rstrip() + "\n"


def build_monthly_report(ts: datetime) -> str:
    monthly = _journal_metrics(30)
    strategy = _strategy_metrics(30)
    live = _live_readiness_metrics()
    lines = _markdown_header("Monthly Strategy Review Report", ts)
    lines += [
        "## Monthly Review",
        "",
        f"- Strategy under review: `{strategy['strategy_name']}`",
        f"- Trades closed: `{monthly['trades_closed']}`",
        f"- Win rate: `{monthly['win_rate_pct']}%`",
        f"- Net R: `{monthly['net_r']}`",
        f"- Profit factor: `{monthly['profit_factor']}`",
        f"- Max drawdown: `{monthly['max_drawdown_r']}R`",
        f"- Best setup: `{strategy['best_setup']}`",
        f"- Worst setup: `{strategy['worst_setup']}`",
        f"- Robustness status: `{strategy['robustness_status']}`",
        f"- Current live-readiness verdict: `{live['final_verdict']}`",
        "",
        "## Owner Decision Focus",
        "",
        "- Decide whether the strategy remains in demo/verification or needs revalidation.",
        "- Compare report outcomes with `config/strategy_catalog.yaml` and `docs/OPS02_REVISED_GATE.md`.",
        "",
    ]
    return "\n".join(lines).rstrip() + "\n"


def build_strategy_report(ts: datetime) -> str:
    strategy = _strategy_metrics(30)
    lines = _markdown_header("Strategy Performance Report", ts)
    lines += [
        "## Strategy Metrics",
        "",
        f"- Strategy name: `{strategy['strategy_name']}`",
        f"- Pair: `{strategy['pair']}`",
        f"- Session: `{strategy['session']}`",
        f"- Number of trades: `{strategy['number_of_trades']}`",
        f"- Win rate: `{strategy['win_rate_pct']}%`",
        f"- Gross PF: `{strategy['gross_pf']}`",
        f"- Net PF: `{strategy['net_pf']}`",
        f"- Expectancy: `{strategy['expectancy']}R`",
        f"- Max drawdown: `{strategy['max_drawdown_r']}R`",
        f"- Best setup: `{strategy['best_setup']}`",
        f"- Worst setup: `{strategy['worst_setup']}`",
        f"- Robustness status: `{strategy['robustness_status']}`",
        f"- Recommendation: `{strategy['recommendation']}`",
        "",
    ]
    return "\n".join(lines).rstrip() + "\n"


def build_risk_report(ts: datetime) -> str:
    risk = _risk_metrics(7)
    lines = _markdown_header("Risk Report", ts)
    lines += [
        "## Risk Snapshot",
        "",
        f"- Current exposure: `{risk['current_exposure']}` open positions",
        f"- Daily risk used: `{risk['daily_risk_used_pct']}%`",
        f"- Per-trade risk: `{risk['per_trade_risk_pct']}%`",
        f"- Max drawdown: `{risk['max_drawdown_r']}R`",
        f"- Consecutive losses: `{risk['consecutive_losses']}`",
        f"- Emergency stop status: `{risk['emergency_stop_status']}`",
        f"- Risk breaches: `{', '.join(risk['risk_breaches'])}`",
        f"- Recommendation: `{risk['recommendation']}`",
        "",
    ]
    return "\n".join(lines).rstrip() + "\n"


def build_execution_report(ts: datetime) -> str:
    execution = _execution_metrics()
    lines = _markdown_header("Execution Quality Report", ts)
    lines += [
        "## Execution Metrics",
        "",
        f"- Data source: `{execution['source']}`",
        f"- Signal to order latency avg: `{execution['signal_to_order_avg_ms'] if execution['signal_to_order_avg_ms'] is not None else 'n/a'} ms`",
        f"- Order to fill latency avg: `{execution['order_to_fill_avg_ms'] if execution['order_to_fill_avg_ms'] is not None else 'n/a'} ms`",
        f"- Orders filled: `{execution['orders_filled']}`",
        f"- Orders rejected: `{execution['orders_rejected']}`",
        f"- Fill rate: `{execution['fill_rate']}`",
        f"- Reject reasons: `{json.dumps(execution['reject_reasons'], sort_keys=True)}`",
        f"- Slippage summary available: `{bool(execution['slippage'])}`",
        f"- Reconnect data available: `{bool(execution['reconnects'])}`",
        "",
    ]
    return "\n".join(lines).rstrip() + "\n"


def build_system_health_report(ts: datetime) -> str:
    health = _health_snapshot()
    log_count = health["logs"]["error_count"]
    missing_data = "YES" if not TRADE_EVENT_LOG.exists() and not TRADE_DB.exists() else "NO"
    lines = _markdown_header("System Health Report", ts)
    lines += [
        "## Health Checks",
        "",
        f"- Database connection: `{health['database']['status']}`",
        f"- Broker/API connection: `{health['broker']['status']}`",
        f"- Worker service status: `{health['runner']['status']}`",
        f"- Log errors: `{log_count}`",
        f"- Missing data: `{missing_data}`",
        f"- Heartbeat status: `{health['recovery']['status']}`",
        f"- Last successful run: `{health['logs']['last_success_line'] or 'n/a'}`",
        f"- Critical alerts: `{health['logs']['critical_count']}`",
        "",
        "## Database Health",
        "",
        f"- Backend verdict: `{health['database']['detail']}`",
        "",
    ]
    return "\n".join(lines).rstrip() + "\n"


def build_database_health_report(ts: datetime) -> str:
    health = _health_snapshot()
    lines = _markdown_header("Database Health Report", ts)
    lines += [
        "## Database Health",
        "",
        f"- Database connection: `{health['database']['status']}`",
        f"- Detail: `{health['database']['detail']}`",
        f"- Recovery state: `{health['recovery']['status']}`",
        f"- Trade DB present: `{TRADE_DB.exists()}`",
        f"- Event log present: `{TRADE_EVENT_LOG.exists()}`",
        "",
    ]
    return "\n".join(lines).rstrip() + "\n"


def build_incident_report(ts: datetime) -> str:
    incidents = _incident_metrics(7)
    health = _health_snapshot()
    lines = _markdown_header("Incident Report", ts)
    lines += [
        "## Incident Summary",
        "",
        f"- Incident count: `{incidents['incident_count']}`",
        f"- Critical incident count: `{incidents['critical_count']}`",
        f"- Runner status: `{health['runner']['status']}`",
        f"- Recovery status: `{health['recovery']['status']}`",
        "",
        "## Recent Incident Lines",
        "",
    ]
    if incidents["recent_lines"]:
        lines.extend(f"- `{line[-180:]}`" for line in incidents["recent_lines"][-10:])
    else:
        lines.append("- `No recent incidents found in scanned logs.`")
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def build_live_readiness_report(ts: datetime) -> str:
    live = _live_readiness_metrics()
    lines = _markdown_header("Live Readiness Report", ts)
    lines += [
        "## Readiness Gate",
        "",
        f"- Validation gate status: `{live['validation_gate_status']}`",
        f"- Paper trading result: `{live['paper_trading_result']}`",
        f"- Execution stability: `{live['execution_stability']}`",
        f"- Database stability: `{live['database_stability']}`",
        f"- Risk firewall status: `{live['risk_firewall_status']}`",
        f"- Governance status: `{live['governance_status']}`",
        f"- Emergency stop test: `{live['emergency_stop_test']}`",
        f"- Incident count: `{live['incident_count']}`",
        f"- Final verdict: `{live['final_verdict']}`",
        "",
    ]
    return "\n".join(lines).rstrip() + "\n"


BUILDERS = {
    "daily": build_daily_report,
    "weekly": build_weekly_report,
    "monthly": build_monthly_report,
    "strategy": build_strategy_report,
    "risk": build_risk_report,
    "execution": build_execution_report,
    "system-health": build_system_health_report,
    "database-health": build_database_health_report,
    "incident": build_incident_report,
    "live-readiness": build_live_readiness_report,
}


def generate_report(report_type: str, *, root: Path = ROOT, generated_at: datetime | None = None) -> Path:
    if report_type not in BUILDERS:
        raise ValueError(f"Unsupported report type: {report_type}")
    generated_at = generated_at or _now()
    ensure_report_dirs(root)
    path = _report_path(report_type, generated_at, root)
    body = BUILDERS[report_type](generated_at)
    path.write_text(body, encoding="utf-8")
    return path


def generate_many(report_type: str, *, root: Path = ROOT, generated_at: datetime | None = None) -> list[ReportArtifact]:
    generated_at = generated_at or _now()
    if report_type == "all":
        return [
            ReportArtifact(kind, generate_report(kind, root=root, generated_at=generated_at))
            for kind in BUILDERS
            if kind != "database-health"
        ]
    return [ReportArtifact(report_type, generate_report(report_type, root=root, generated_at=generated_at))]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate trading platform reports")
    parser.add_argument("--type", required=True, choices=SUPPORTED_TYPES, help="Report type to generate")
    args = parser.parse_args(argv)

    try:
        artifacts = generate_many(args.type)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    for artifact in artifacts:
        print(artifact.path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
