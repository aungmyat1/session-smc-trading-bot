"""
Strategy Demo System Health Check — deployment readiness status.

Checks:
  Runner      — log file exists and has recent activity
  Broker      — MetaAPI connection, heartbeat, latency
  Data Feed   — live price fetch for each pair
  Research DB — optional PostgreSQL reachability for research services
  Risk Engine — daily limits, open positions, loss guards
  Portfolio   — portfolio manager loss limits
  Execution   — TRADING_MODE, DEMO_ONLY guard, LIVE_TRADING block

Output:
  SYSTEM STATUS
  Runner:           PASS / WARN / FAIL
  Broker:           PASS / WARN / FAIL
  Data Feed:        PASS / WARN / FAIL
  Risk Engine:      PASS / FAIL
  Portfolio:        PASS / FAIL
  Execution:        READY / SHADOW / BLOCKED

Usage:
    python3 scripts/health_check.py
    python3 scripts/health_check.py --no-broker   (skip live connection)
    python3 scripts/health_check.py --json         (machine-readable)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import socket
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

from research.lineage import build_release_metadata

try:
    from dotenv import load_dotenv
    load_dotenv(_ROOT / ".env")
except ImportError:
    pass

try:
    import yaml
except ImportError:  # pragma: no cover - optional in minimal runtimes
    yaml = None

_RUNNER_LOGS = [
    _ROOT / "logs" / "strategy_demo.log",
    _ROOT / "logs" / "st_a2_demo.log",
    _ROOT / "logs" / "st_a2_runner.log",
]
_PAIRS       = ["EURUSD", "XAUUSD"]
_STALE_S     = 300   # runner log is stale if no entry within 5 min
_CONNECT_TIMEOUT_S = 45
_RPC_TIMEOUT_S = 20
_DB_CONNECT_TIMEOUT_S = 3
_DB_FAIL_THRESHOLD = int(os.environ.get("DB_HEALTHCHECK_FAIL_THRESHOLD", "3"))
_DB_BACKEND_CHOICES = {"auto", "postgres", "duckdb", "sqlite", "disabled"}
_CONTROL_STATE_PATH = _ROOT / "reports" / "control_state.json"
_DB_HEALTH_STATE_PATH = _ROOT / "logs" / "db_health_state.json"

# ── Individual checks ──────────────────────────────────────────────────────────


def check_runner() -> dict:
    active_log = next((path for path in _RUNNER_LOGS if path.exists()), None)
    if active_log is None:
        return {"status": "FAIL", "detail": "strategy demo runner log not found"}

    age_s = datetime.now().timestamp() - active_log.stat().st_mtime
    try:
        lines    = active_log.read_text(errors="replace").splitlines()
        last_line = next((line for line in reversed(lines) if line.strip()), "")
    except OSError:
        last_line = ""

    if age_s > _STALE_S:
        return {
            "status": "WARN",
            "detail": f"last activity {int(age_s)}s ago (>{_STALE_S}s)",
            "last_line": last_line[-120:],
        }
    return {"status": "PASS", "detail": f"active ({int(age_s)}s ago)", "last_line": last_line[-120:]}


async def check_broker() -> dict:
    try:
        from execution.mt5_connector import MT5Connector
        conn = MT5Connector(mode="demo")
        await asyncio.wait_for(conn.connect(), timeout=_CONNECT_TIMEOUT_S)
        hb = await asyncio.wait_for(conn.heartbeat(), timeout=_RPC_TIMEOUT_S)
        await conn.disconnect()
    except Exception as exc:
        return {"status": "FAIL", "detail": str(exc)[:200]}

    if not hb["connected"]:
        return {"status": "FAIL", "detail": "heartbeat returned disconnected"}
    lat = hb["latency_ms"]
    if lat > 500:
        return {"status": "WARN", "detail": f"high latency {lat}ms", "latency_ms": lat}
    return {"status": "PASS", "detail": f"connected latency={lat}ms", "latency_ms": lat}


async def check_data_feed() -> dict:
    _MAX_SP = {"EURUSD": 1.5, "XAUUSD": 3.0}
    try:
        from execution.mt5_connector import MT5Connector
        from execution.vantage_demo_executor import VantageDemoExecutor
        conn = MT5Connector(mode="demo")
        await asyncio.wait_for(conn.connect(), timeout=_CONNECT_TIMEOUT_S)
        ex   = VantageDemoExecutor(conn)
        pairs: dict = {}
        for sym in _PAIRS:
            try:
                px = await asyncio.wait_for(ex.get_price(sym), timeout=_RPC_TIMEOUT_S)
                pairs[sym] = {
                    "bid": px["bid"],
                    "spread_pips": px["spread_pips"],
                    "within_limit": px["spread_pips"] <= _MAX_SP.get(sym, 2.0),
                }
            except Exception as exc:
                pairs[sym] = {"error": str(exc)[:100]}
        await conn.disconnect()
    except Exception as exc:
        return {"status": "FAIL", "detail": str(exc)[:200]}

    errors = [s for s, v in pairs.items() if "error" in v]
    wide   = [s for s, v in pairs.items() if not v.get("within_limit", True)]
    if errors:
        return {"status": "FAIL", "detail": f"fetch failed: {errors}", "pairs": pairs}
    if wide:
        return {"status": "WARN", "detail": f"spread too wide: {wide}", "pairs": pairs}
    return {"status": "PASS", "detail": "all pairs reachable", "pairs": pairs}


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _load_db_health_state() -> dict:
    if not _DB_HEALTH_STATE_PATH.exists():
        return {}
    try:
        payload = json.loads(_DB_HEALTH_STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_db_health_state(state: dict) -> None:
    _DB_HEALTH_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _DB_HEALTH_STATE_PATH.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


def _record_db_probe_result(endpoint_key: str, ok: bool) -> int:
    state = _load_db_health_state()
    entry = state.get(endpoint_key, {})
    if not isinstance(entry, dict):
        entry = {}
    count = 0 if ok else int(entry.get("consecutive_failures", 0)) + 1
    state[endpoint_key] = {
        "consecutive_failures": count,
        "last_result": "PASS" if ok else "FAIL",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    _write_db_health_state(state)
    return count


def _load_yaml(path: Path) -> dict:
    if yaml is None or not path.exists():
        return {}
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _load_control_state() -> dict:
    if not _CONTROL_STATE_PATH.exists():
        return {}
    try:
        payload = json.loads(_CONTROL_STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _emergency_stop_state() -> dict:
    state = _load_control_state().get("emergency_stop", {})
    return state if isinstance(state, dict) else {}


def _in_container_runtime() -> bool:
    return Path("/.dockerenv").exists() or _env_bool("RUNNING_IN_CONTAINER", False)


def _db_probe_candidates(host: str, port: int) -> list[tuple[str, int, str]]:
    candidates: list[tuple[str, int, str]] = [(host, port, "configured")]
    if host in {"127.0.0.1", "localhost"} and _in_container_runtime():
        override = os.environ.get("DB_HEALTHCHECK_HOST", "").strip()
        extras = [override] if override else ["host.docker.internal", "postgres"]
        for extra in extras:
            if extra and all(existing[0] != extra for existing in candidates):
                candidates.append((extra, port, "container_fallback"))
    return candidates


def _probe_socket(host: str, port: int) -> tuple[bool, str]:
    try:
        with socket.create_connection((host, port), timeout=_DB_CONNECT_TIMEOUT_S):
            pass
        return True, "reachable"
    except Exception as exc:
        return False, f"{exc.__class__.__name__}: {exc}"


def _infer_db_backend(explicit_backend: str | None = None) -> tuple[str, dict]:
    backend = (explicit_backend or os.environ.get("DB_BACKEND", "")).strip().lower()
    if backend and backend not in _DB_BACKEND_CHOICES:
        return "unknown", {
            "status": "FAIL",
            "detail": f"invalid DB_BACKEND={backend!r}; expected one of {sorted(_DB_BACKEND_CHOICES)}",
        }

    if backend == "disabled" or not _env_bool("DB_HEALTHCHECK_ENABLED", True):
        return "disabled", {
            "status": "SKIP",
            "detail": "database health check disabled for this runtime mode",
        }

    if backend in {"postgres", "duckdb", "sqlite"}:
        return backend, {}

    database_url = os.environ.get("DATABASE_URL", "").strip()
    if database_url:
        parsed = urlparse(database_url)
        scheme = (parsed.scheme or "").lower()
        if scheme.startswith("postgres"):
            return "postgres", {"database_url": database_url}
        if scheme.startswith("sqlite"):
            return "sqlite", {"database_url": database_url}
        if scheme.startswith("duckdb"):
            return "duckdb", {"database_url": database_url}

    if os.environ.get("DB_HOST") or os.environ.get("DB_PORT") or os.environ.get("DB_NAME"):
        return "postgres", {}

    research_cfg = _load_yaml(_ROOT / "config" / "research_engine.yaml")
    duckdb_path = str(research_cfg.get("analytics", {}).get("duckdb_path", "")).strip()
    if duckdb_path:
        return "duckdb", {"duckdb_path": duckdb_path}

    return "unknown", {
        "status": "FAIL",
        "detail": (
            "missing database runtime config; set DB_BACKEND=postgres|duckdb|sqlite|disabled "
            "or provide DATABASE_URL / config/research_engine.yaml"
        ),
    }


def _postgres_service_status() -> str:
    try:
        proc = subprocess.run(
            ["systemctl", "is-active", "postgresql"],
            capture_output=True,
            text=True,
            check=False,
            timeout=2,
        )
    except Exception:
        return "unknown"
    status = (proc.stdout or proc.stderr or "").strip()
    return status or "unknown"


def check_research_db(db_backend: str | None = None) -> dict:
    """
    Probe the runtime database backend.

    This is strict for required postgres runtimes and a no-op for DuckDB,
    SQLite, or explicitly disabled database modes.
    """
    backend, meta = _infer_db_backend(db_backend)
    if backend == "unknown":
        return meta

    if backend == "disabled":
        return meta

    if backend in {"duckdb", "sqlite"}:
        path = meta.get("duckdb_path") or meta.get("database_url") or "local file"
        return {
            "status": "SKIP",
            "detail": f"{backend} runtime selected; no localhost:5432 check required ({path})",
        }

    database_url = meta.get("database_url") or os.environ.get("DATABASE_URL", "")
    parsed = urlparse(database_url) if database_url else None
    host = parsed.hostname if parsed and parsed.hostname else os.environ.get("DB_HOST", "localhost")
    port = parsed.port if parsed and parsed.port else int(os.environ.get("DB_PORT", "5432"))
    db_name = parsed.path.lstrip("/") if parsed and parsed.path else os.environ.get("DB_NAME", "")
    db_user = parsed.username if parsed and parsed.username else os.environ.get("DB_USER", "")
    required = backend == "postgres"
    service_status = _postgres_service_status()
    endpoint_key = f"{db_user or '?'}@{host}:{port}/{db_name or '?'}"
    attempts = _db_probe_candidates(host, port)
    errors: list[str] = []
    fallback_success: tuple[str, int, str] | None = None

    for candidate_host, candidate_port, source in attempts:
        ok, detail = _probe_socket(candidate_host, candidate_port)
        if ok:
            if source == "configured":
                _record_db_probe_result(endpoint_key, True)
                return {
                    "status": "PASS",
                    "detail": (
                        f"postgres required={required} host={candidate_host}:{candidate_port} db={db_name or '?'} "
                        f"user={db_user or '?'} service={service_status} reachable"
                    ),
                    "consecutive_failures": 0,
                }
            fallback_success = (candidate_host, candidate_port, source)
            break
        errors.append(f"{candidate_host}:{candidate_port} -> {detail}")

    if fallback_success is not None:
        _record_db_probe_result(endpoint_key, True)
        candidate_host, candidate_port, _source = fallback_success
        return {
            "status": "WARN",
            "detail": (
                f"postgres configured host={host}:{port} unreachable but fallback {candidate_host}:{candidate_port} reachable; "
                f"db={db_name or '?'} user={db_user or '?'} service={service_status}"
            ),
            "consecutive_failures": 0,
            "configured_host": host,
            "effective_host": candidate_host,
        }

    consecutive_failures = _record_db_probe_result(endpoint_key, False)
    escalated = consecutive_failures >= max(1, _DB_FAIL_THRESHOLD)
    status = "FAIL" if required and escalated else "WARN"
    return {
        "status": status,
        "detail": (
            f"postgres required={required} host={host}:{port} db={db_name or '?'} "
            f"user={db_user or '?'} service={service_status} "
            f"-> unreachable after {consecutive_failures} consecutive failure(s); "
            f"threshold={_DB_FAIL_THRESHOLD}; attempts=[{'; '.join(errors)}]"
        ),
        "consecutive_failures": consecutive_failures,
        "alert_eligible": escalated,
    }


def check_risk_engine() -> dict:
    emergency = _emergency_stop_state()
    if emergency.get("active"):
        reason = emergency.get("reason", "dashboard emergency stop active")
        return {
            "status": "FAIL",
            "detail": f"blocked: EMERGENCY_STOP ({reason})",
            "emergency_stop": emergency,
        }

    state_path = _ROOT / "logs" / "bot_state.json"
    state: dict = {}
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text())
        except Exception:
            pass

    from execution.demo_risk_manager import check_limits, LIMITS
    result = check_limits(state)
    if not result["approved"]:
        return {"status": "FAIL", "detail": f"blocked: {result['reason']}", "state": state}

    trades = state.get("trades_today", 0)
    cap    = LIMITS["max_trades_per_day"]
    return {
        "status": "PASS",
        "detail": (f"trades={trades}/{cap}  "
                   f"consec_L={state.get('consecutive_losses', 0)}  "
                   f"daily_loss={state.get('daily_loss_pct', 0.0):.2%}"),
    }


def check_portfolio() -> dict:
    from core.portfolio_manager import PortfolioManager
    pm    = PortfolioManager()
    stats = pm.stats()
    if pm.any_loss_limit_hit():
        return {"status": "FAIL", "detail": "portfolio loss limit triggered", "stats": stats}
    return {
        "status": "PASS",
        "detail": (f"daily={stats['daily_pnl_pct']:+.3f}%  "
                   f"weekly={stats['weekly_pnl_pct']:+.3f}%"),
    }


def check_execution() -> dict:
    emergency = _emergency_stop_state()
    if emergency.get("active"):
        reason = emergency.get("reason", "dashboard emergency stop active")
        return {
            "status": "BLOCKED",
            "detail": f"EMERGENCY_STOP active — {reason}",
            "emergency_stop": emergency,
        }

    mode      = os.environ.get("TRADING_MODE", "shadow").lower()
    demo_only = os.environ.get("DEMO_ONLY", "true").lower() not in ("false", "0", "no")
    live      = os.environ.get("LIVE_TRADING", "false").lower() in ("true", "1", "yes")

    if live or mode == "live":
        return {"status": "BLOCKED",
                "detail": "LIVE_TRADING or TRADING_MODE=live — see CLAUDE.md §0"}
    if mode == "shadow" or demo_only:
        return {"status": "SHADOW",
                "detail": f"mode={mode}  DEMO_ONLY={demo_only}  (no live orders)"}
    return {"status": "READY",
            "detail": f"mode={mode}  DEMO_ONLY={demo_only}  LIVE_TRADING={live}"}


def check_journal() -> dict:
    from core.trade_journal_db import TradeJournalDB
    try:
        s = TradeJournalDB().summary()
        return {"status": "PASS", "summary": s,
                "detail": (f"total={s['total']}  open={s['open']}  "
                           f"closed={s['closed']}  W={s['wins']}  L={s['losses']}")}
    except Exception as exc:
        return {"status": "FAIL", "detail": str(exc)[:200]}


def check_recovery() -> dict:
    state_path = _ROOT / "logs" / "bot_state.json"
    journal_path = _ROOT / "logs" / "trades.jsonl"
    state: dict = {}
    journal_stats: dict = {"records": 0, "signals": 0, "orders": 0, "fills": 0, "rejections": 0, "closes": 0}

    if state_path.exists():
        try:
            state = json.loads(state_path.read_text())
        except Exception:
            return {"status": "WARN", "detail": "bot_state.json exists but could not be parsed", "state_file": str(state_path)}

    if journal_path.exists():
        try:
            lines = [line for line in journal_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            journal_stats["records"] = len(lines)
            for line in lines:
                try:
                    event = json.loads(line)
                except Exception:
                    continue
                event_type = event.get("event")
                if event_type == "SIGNAL_CREATED":
                    journal_stats["signals"] += 1
                elif event_type == "ORDER_SUBMITTED":
                    journal_stats["orders"] += 1
                elif event_type == "ORDER_FILLED":
                    journal_stats["fills"] += 1
                elif event_type == "ORDER_REJECTED":
                    journal_stats["rejections"] += 1
                elif event_type == "POSITION_CLOSED":
                    journal_stats["closes"] += 1
        except Exception as exc:
            return {"status": "WARN", "detail": f"trade journal unreadable: {exc}", "state": state}

    if not state and not journal_stats["records"]:
        return {"status": "WARN", "detail": "no restart recovery state found", "state": state, "journal": journal_stats}

    return {
        "status": "PASS",
        "detail": (
            f"state_loaded={bool(state)} journal_records={journal_stats['records']} "
            f"signals={journal_stats['signals']} fills={journal_stats['fills']} closes={journal_stats['closes']}"
        ),
        "state": state,
        "journal": journal_stats,
    }


# ── Output ─────────────────────────────────────────────────────────────────────

_ICON = {"PASS": "✓", "WARN": "~", "FAIL": "✗",
         "READY": "✓", "SHADOW": "~", "BLOCKED": "✗", "SKIP": "-"}


def _fmt(label: str, r: dict, w: int = 14) -> str:
    st   = r.get("status", "?")
    icon = _ICON.get(st, "?")
    return f"  {label:<{w}}  {icon} {st:<8}  {r.get('detail', '')}"


async def _run_all(no_broker: bool, no_db: bool, db_backend: str | None = None) -> dict:
    results: dict[str, dict] = {}
    results["Runner"]      = check_runner()
    results["Risk Engine"] = check_risk_engine()
    results["Recovery"]    = check_recovery()
    results["Portfolio"]   = check_portfolio()
    results["Execution"]   = check_execution()
    results["Journal"]     = check_journal()
    results["Research DB"] = {"status": "SKIP", "detail": "--no-db"} if no_db else check_research_db(db_backend)
    if not no_broker:
        results["Broker"]    = await check_broker()
        results["Data Feed"] = await check_data_feed()
    else:
        results["Broker"]    = {"status": "SKIP", "detail": "--no-broker"}
        results["Data Feed"] = {"status": "SKIP", "detail": "--no-broker"}
    return results


def _verdict(results: dict) -> str:
    statuses = {r["status"] for r in results.values()}
    if "FAIL" in statuses or "BLOCKED" in statuses:
        return "NOT READY"
    if "WARN" in statuses or "SHADOW" in statuses:
        return "READY (shadow mode)"
    return "READY"


def main() -> None:
    parser = argparse.ArgumentParser(description="ST-A2 health check")
    parser.add_argument("--no-broker", action="store_true",
                        help="Skip broker connection (offline-safe)")
    parser.add_argument("--no-db", action="store_true",
                        help="Skip research database reachability probe")
    parser.add_argument(
        "--db-backend",
        choices=sorted(_DB_BACKEND_CHOICES),
        default=os.environ.get("DB_BACKEND", "auto"),
        help="Override the DB runtime mode for this health check",
    )
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()

    if args.db_backend:
        os.environ["DB_BACKEND"] = args.db_backend

    results = asyncio.run(_run_all(args.no_broker, args.no_db, args.db_backend))
    now     = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    if args.as_json:
        print(json.dumps({"timestamp": now, "checks": results,
                          "verdict": _verdict(results),
                          "release": build_release_metadata()}, indent=2))
        return

    print()
    print("=" * 62)
    print(f"  SYSTEM STATUS   {now}")
    print("=" * 62)
    print()
    for label, r in results.items():
        print(_fmt(label, r))
    print()
    v    = _verdict(results)
    icon = "✓" if "READY" in v else "✗"
    print(f"  Overall:  {icon} {v}")
    print("=" * 62)

    j = results.get("Journal", {}).get("summary", {})
    if j.get("total", 0) > 0:
        print()
        print(f"  Journal: {j['total']} records  "
              f"open={j['open']}  closed={j['closed']}  "
              f"W={j['wins']}  L={j['losses']}  "
              f"avgR={j['avg_r']}  PF={j['profit_factor']}")
    print()


if __name__ == "__main__":
    main()
