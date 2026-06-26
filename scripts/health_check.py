"""
ST-A2 System Health Check — deployment readiness status.

Checks:
  Runner      — log file exists and has recent activity
  Broker      — MetaAPI connection, heartbeat, latency
  Data Feed   — live price fetch for each pair
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
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(_ROOT / ".env")
except ImportError:
    pass

_RUNNER_LOG  = _ROOT / "logs" / "st_a2_runner.log"
_PAIRS       = ["EURUSD", "XAUUSD"]
_STALE_S     = 300   # runner log is stale if no entry within 5 min
_CONNECT_TIMEOUT_S = 45
_RPC_TIMEOUT_S = 20

# ── Individual checks ──────────────────────────────────────────────────────────


def check_runner() -> dict:
    if not _RUNNER_LOG.exists():
        return {"status": "FAIL", "detail": "logs/st_a2_runner.log not found"}

    age_s = datetime.now().timestamp() - _RUNNER_LOG.stat().st_mtime
    try:
        lines    = _RUNNER_LOG.read_text(errors="replace").splitlines()
        last_line = next((l for l in reversed(lines) if l.strip()), "")
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


def check_risk_engine() -> dict:
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


# ── Output ─────────────────────────────────────────────────────────────────────

_ICON = {"PASS": "✓", "WARN": "~", "FAIL": "✗",
         "READY": "✓", "SHADOW": "~", "BLOCKED": "✗", "SKIP": "-"}


def _fmt(label: str, r: dict, w: int = 14) -> str:
    st   = r.get("status", "?")
    icon = _ICON.get(st, "?")
    return f"  {label:<{w}}  {icon} {st:<8}  {r.get('detail', '')}"


async def _run_all(no_broker: bool) -> dict:
    results: dict[str, dict] = {}
    results["Runner"]      = check_runner()
    results["Risk Engine"] = check_risk_engine()
    results["Portfolio"]   = check_portfolio()
    results["Execution"]   = check_execution()
    results["Journal"]     = check_journal()
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
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()

    results = asyncio.run(_run_all(args.no_broker))
    now     = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    if args.as_json:
        print(json.dumps({"timestamp": now, "checks": results,
                          "verdict": _verdict(results)}, indent=2))
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
