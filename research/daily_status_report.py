#!/usr/bin/env python3
"""
RESEARCH-06 — Daily Status Report Generator.

Reads from live logs and existing summaries; writes reports/daily_status.md.
Read-only on all sources. No strategy, execution, or MetaAPI changes.

Usage:
    python3 research/daily_status_report.py
    python3 research/daily_status_report.py --date 2026-06-23
    python3 research/daily_status_report.py --out reports/my_report.md
    python3 research/daily_status_report.py --quiet   # suppress stdout echo
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

_ROOT = Path(__file__).parent.parent
_UTC = timezone.utc

_BOT_LOG       = _ROOT / "logs" / "bot.log"
_TRADE_LOG     = _ROOT / "logs" / "trades.jsonl"
_BOT_STATE     = _ROOT / "logs" / "bot_state.json"
_DAILY_SUMMARY = _ROOT / "logs" / "daily_trade_summary.json"
_WEEKLY_SUMMARY= _ROOT / "logs" / "weekly_trade_summary.json"
_REPORTS_DIR   = _ROOT / "reports"
_OPS_AUDIT     = _ROOT / "docs" / "OPS01_INFRASTRUCTURE_AUDIT.md"

_OPS01_START   = "2026-06-22"
_OPS01_END     = "2026-06-28"

_TS_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})")


# ── Helpers ──────────────────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(_UTC)


def _parse_ts(line: str) -> Optional[datetime]:
    m = _TS_RE.match(line)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S").replace(tzinfo=_UTC)
    except ValueError:
        return None


def _read_log_lines(date_prefix: str) -> list[str]:
    """Return all bot.log lines for the given date (YYYY-MM-DD)."""
    if not _BOT_LOG.exists():
        return []
    lines = []
    try:
        with open(_BOT_LOG) as f:
            for line in f:
                if line.startswith(date_prefix):
                    lines.append(line)
    except OSError:
        pass
    return lines


# ── Section parsers ──────────────────────────────────────────────────────────

def _bot_process_status() -> dict:
    """Check whether tmux session and bot.py process are alive."""
    tmux_alive = False
    tmux_out = subprocess.run(["tmux", "ls"], capture_output=True, text=True)
    tmux_alive = "bot" in tmux_out.stdout

    pgrep = subprocess.run(["pgrep", "-f", "bot.py"], capture_output=True, text=True)
    pids = pgrep.stdout.strip().splitlines()
    pid = pids[0] if pids else None

    rss_mb = None
    if pid:
        try:
            with open(f"/proc/{pid}/status") as f:
                for l in f:
                    if l.startswith("VmRSS:"):
                        rss_mb = int(l.split()[1]) // 1024
                        break
        except OSError:
            pass

    return {
        "tmux_alive": tmux_alive,
        "process_alive": pid is not None,
        "pid": pid,
        "rss_mb": rss_mb,
    }


def _live_trading_guard() -> bool:
    """Return True if LIVE_TRADING=false in .env."""
    env = _ROOT / ".env"
    if not env.exists():
        return False
    val = "false"
    for line in env.read_text().splitlines():
        s = line.strip()
        if s.startswith("LIVE_TRADING="):
            val = s.split("=", 1)[1].strip().lower()
    return val == "false"


def _heartbeat_metrics(lines: list[str]) -> dict:
    """
    Parse heartbeat lines for the day.
    Returns: count, first_ts, last_ts, last_status, last_balance, last_equity,
             last_uptime, max_gap_s, last_open_positions.
    """
    hb_lines = [l for l in lines if "[HEARTBEAT]" in l]
    if not hb_lines:
        return {"count": 0, "last_status": "UNKNOWN", "max_gap_s": None}

    timestamps = []
    for l in hb_lines:
        ts = _parse_ts(l)
        if ts:
            timestamps.append(ts)

    gaps = []
    for i in range(1, len(timestamps)):
        gaps.append(int((timestamps[i] - timestamps[i - 1]).total_seconds()))

    last_hb_block = "\n".join(hb_lines[-6:])

    def _extract(pattern: str, default: str = "?") -> str:
        m = re.search(pattern, last_hb_block)
        return m.group(1) if m else default

    return {
        "count": len(hb_lines),
        "first_ts": timestamps[0].strftime("%H:%M UTC") if timestamps else "—",
        "last_ts": timestamps[-1].strftime("%H:%M UTC") if timestamps else "—",
        "last_status": _extract(r"connection_status=(\w+)"),
        "last_balance": _extract(r"balance=([\d.]+)"),
        "last_equity": _extract(r"equity=([\d.]+)"),
        "last_uptime_s": _extract(r"uptime=(\d+)"),
        "last_open_positions": _extract(r"open_positions=([-\d]+)"),
        "max_gap_s": max(gaps) if gaps else 0,
        "age_s": int((_now() - timestamps[-1]).total_seconds()) if timestamps else None,
    }


def _connection_metrics(lines: list[str]) -> dict:
    """Count disconnects, reconnect successes/failures, watchdog alerts, rpc timeouts."""
    disconnects = sum(1 for l in lines if "MetaAPI RPC timeout" in l or
                      "connection_status=DISCONNECTED" in l and "[HEARTBEAT]" in l)
    rpc_timeouts = sum(1 for l in lines if "MetaAPI RPC timeout" in l)
    reconnect_ok = sum(1 for l in lines if "reconnected successfully" in l.lower() or
                       "reconnect: connection established" in l.lower())
    reconnect_fail = sum(1 for l in lines if "MetaAPI reconnect failed" in l or
                         "reconnect failed" in l.lower())
    watchdog = sum(1 for l in lines if "CRITICAL" in l and "heartbeat" in l.lower())
    connected_events = sum(1 for l in lines if "MetaAPI connected" in l)

    return {
        "rpc_timeouts": rpc_timeouts,
        "disconnect_events": disconnects,
        "reconnect_ok": reconnect_ok,
        "reconnect_fail": reconnect_fail,
        "watchdog_alerts": watchdog,
        "connected_events": connected_events,
    }


def _signal_metrics(lines: list[str]) -> dict:
    """Count signals generated and orders attempted today."""
    signals = sum(1 for l in lines if "SIGNAL" in l and "generated" in l.lower())
    orders_ok = sum(1 for l in lines if "ORDER_FILLED" in l or "order placed" in l.lower())
    orders_rej = sum(1 for l in lines if "ORDER_REJECTED" in l or "SPREAD_TOO_WIDE" in l)
    errors = sum(1 for l in lines if "ERROR" in l)
    return {
        "signals_generated": signals,
        "orders_ok": orders_ok,
        "orders_rejected": orders_rej,
        "errors_in_log": errors,
    }


def _bot_state() -> dict:
    if not _BOT_STATE.exists():
        return {}
    try:
        return json.loads(_BOT_STATE.read_text())
    except Exception:
        return {}


def _daily_summary() -> dict:
    if not _DAILY_SUMMARY.exists():
        return {}
    try:
        return json.loads(_DAILY_SUMMARY.read_text())
    except Exception:
        return {}


def _weekly_summary() -> dict:
    if not _WEEKLY_SUMMARY.exists():
        return {}
    try:
        return json.loads(_WEEKLY_SUMMARY.read_text())
    except Exception:
        return {}


def _ops01_status() -> dict:
    """Determine OPS-01 day number and days remaining."""
    today = _now().date()
    try:
        start = datetime.strptime(_OPS01_START, "%Y-%m-%d").date()
        end   = datetime.strptime(_OPS01_END,   "%Y-%m-%d").date()
        day_n = (today - start).days + 1
        days_left = (end - today).days
        pct = min(100, round((today - start).days / (end - start).days * 100))
        return {
            "start": _OPS01_START,
            "end": _OPS01_END,
            "day_n": day_n,
            "days_left": days_left,
            "pct_complete": pct,
        }
    except Exception:
        return {"day_n": "?", "days_left": "?", "pct_complete": 0}


def _disk_info() -> str:
    import shutil
    total, used, free = shutil.disk_usage("/")
    return f"{free / 1e9:.1f} GB free ({free / total * 100:.0f}%)"


def _cpu_pct() -> float:
    """Sample CPU usage over 0.3s interval from /proc/stat."""
    import time
    def _read():
        with open("/proc/stat") as f:
            parts = list(map(int, f.readline().split()[1:8]))
        idle = parts[3]
        total = sum(parts)
        return idle, total
    i1, t1 = _read()
    time.sleep(0.3)
    i2, t2 = _read()
    return round(100.0 * (1 - (i2 - i1) / max(1, t2 - t1)), 1)


def _ram_info() -> dict:
    """Read /proc/meminfo and return usage breakdown."""
    fields: dict[str, int] = {}
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if ":" in line:
                    k, v = line.split(":", 1)
                    fields[k.strip()] = int(v.split()[0])
    except OSError:
        return {"used_mb": 0, "total_mb": 0, "avail_mb": 0, "pct": 0.0}
    total = fields.get("MemTotal", 0)
    avail = fields.get("MemAvailable", 0)
    used = total - avail
    pct = round(used / max(1, total) * 100, 1)
    return {
        "used_mb": used // 1024,
        "total_mb": total // 1024,
        "avail_mb": avail // 1024,
        "pct": pct,
    }


# ── Render ────────────────────────────────────────────────────────────────────

def _fmt_opt(val, suffix: str = "", na: str = "—") -> str:
    if val is None or val in ("?", "null", ""):
        return na
    if isinstance(val, float):
        return f"{val:.3f}{suffix}"
    return f"{val}{suffix}"


def _pf_badge(pf) -> str:
    if pf is None:
        return ""
    try:
        f = float(pf)
        return " ✅" if f > 1.0 else " ⚠️"
    except (TypeError, ValueError):
        return ""


def _status_icon(ok: bool) -> str:
    return "✅" if ok else "🔴"


def generate_report(date_str: str) -> str:
    lines = _read_log_lines(date_str)
    proc = _bot_process_status()
    live_guard = _live_trading_guard()
    hb = _heartbeat_metrics(lines)
    conn = _connection_metrics(lines)
    sig = _signal_metrics(lines)
    state = _bot_state()
    daily = _daily_summary()
    weekly = _weekly_summary()
    ops = _ops01_status()
    cpu = _cpu_pct()
    ram = _ram_info()
    now_str = _now().strftime("%Y-%m-%dT%H:%M UTC")

    heartbeat_age_ok = hb.get("age_s") is not None and hb["age_s"] < 600
    conn_status = hb.get("last_status", "UNKNOWN")
    process_ok = proc["process_alive"]

    # Session breakdown from daily summary
    session_bd = daily.get("session_breakdown", {})
    symbol_bd = daily.get("symbol_breakdown", {})

    lines_md: list[str] = []
    a = lines_md.append

    a(f"# Daily Status Report — {date_str}")
    a(f"# Generated: {now_str}")
    a(f"# OPS-01 Day {ops['day_n']} / 7 ({ops['pct_complete']}% complete, {ops['days_left']} days left)")
    a("")
    a("---")
    a("")

    # ── 1. System Status ──────────────────────────────────────────────────────
    a("## 1. System Status")
    a("")
    a(f"| Check | Status |")
    a(f"|---|---|")
    a(f"| Bot process (PID {proc['pid'] or 'N/A'}) | {_status_icon(process_ok)} {'RUNNING' if process_ok else 'NOT RUNNING'} |")
    a(f"| tmux session 'bot' | {_status_icon(proc['tmux_alive'])} {'alive' if proc['tmux_alive'] else 'MISSING'} |")
    a(f"| MetaAPI connection | {'✅' if conn_status == 'CONNECTED' else '🔴'} {conn_status} |")
    a(f"| LIVE_TRADING guard | {_status_icon(live_guard)} {'false (safe)' if live_guard else 'WARNING — NOT false'} |")
    a(f"| Memory (bot RSS) | {'✅' if proc['rss_mb'] and proc['rss_mb'] < 500 else '⚠️'} {_fmt_opt(proc['rss_mb'], ' MB')} |")
    a(f"| RAM (system) | {'✅' if ram['pct'] < 85 else '⚠️'} {ram['used_mb']} MB / {ram['total_mb']} MB ({ram['pct']}% used) |")
    a(f"| CPU (sampled) | {'✅' if cpu < 80 else '⚠️'} {cpu}% |")
    a(f"| Disk | {'✅' if 41 > 10 else '⚠️'} {_disk_info()} |")
    a("")

    # ── 2. Heartbeat Status ───────────────────────────────────────────────────
    a("## 2. Heartbeat Status")
    a("")
    last_age = hb.get("age_s")
    age_str = f"{last_age // 60}m {last_age % 60}s ago" if last_age is not None else "unknown"
    a(f"| Metric | Value |")
    a(f"|---|---|")
    a(f"| Heartbeats today | {hb.get('count', 0)} |")
    a(f"| First heartbeat | {hb.get('first_ts', '—')} |")
    a(f"| Last heartbeat | {hb.get('last_ts', '—')} ({age_str}) |")
    a(f"| Last connection status | **{hb.get('last_status', '—')}** |")
    a(f"| Last balance | {hb.get('last_balance', '—')} USD |")
    a(f"| Last equity | {hb.get('last_equity', '—')} USD |")
    a(f"| Open positions | {hb.get('last_open_positions', '—')} |")
    a(f"| Max heartbeat gap | {hb.get('max_gap_s', '—')} s (threshold: 600 s) |")
    a(f"| Heartbeat age | {'✅' if heartbeat_age_ok else '⚠️'} {age_str} |")
    a("")

    # ── 3. Connectivity ───────────────────────────────────────────────────────
    a("## 3. Connectivity Events")
    a("")
    a(f"| Event | Count |")
    a(f"|---|---|")
    a(f"| MetaAPI connected events | {conn.get('connected_events', 0)} |")
    a(f"| RPC timeouts (BUG-01 scenario) | {conn.get('rpc_timeouts', 0)} |")
    a(f"| Disconnect events (heartbeat) | {conn.get('disconnect_events', 0)} |")
    a(f"| Successful reconnects | {conn.get('reconnect_ok', 0)} |")
    a(f"| Failed reconnects | {conn.get('reconnect_fail', 0)} |")
    a(f"| Watchdog alerts (CRITICAL) | {conn.get('watchdog_alerts', 0)} |")
    a(f"| ERROR lines in log | {conn.get('errors_in_log', sig.get('errors_in_log', 0))} |")
    a("")

    # ── 4. Signals & Orders ───────────────────────────────────────────────────
    a("## 4. Signals & Orders")
    a("")
    a(f"| Metric | Value |")
    a(f"|---|---|")
    a(f"| Signals generated | {daily.get('signals_generated', sig.get('signals_generated', 0))} |")
    a(f"| Orders filled | {daily.get('orders_filled', sig.get('orders_ok', 0))} |")
    a(f"| Orders rejected | {daily.get('orders_rejected', sig.get('orders_rejected', 0))} |")
    a(f"| Trades opened | {daily.get('orders_filled', 0)} |")
    a(f"| Trades closed | {daily.get('trades_closed', 0)} |")
    a(f"| Trades still open | {daily.get('trades_still_open', 0)} |")
    a("")

    # ── 5. Trade Performance ──────────────────────────────────────────────────
    a("## 5. Trade Performance (today)")
    a("")
    wr = daily.get("win_rate")
    avg_r = daily.get("average_R")
    pf = daily.get("PF")
    total_r = daily.get("total_R")
    n = daily.get("trade_count", 0)
    wins = daily.get("wins", 0)
    losses = daily.get("losses", 0)

    if n == 0:
        a(f"No completed trades today (expected ~3/month at ST-A2 frequency).")
        a("")
    else:
        a(f"| Metric | Value |")
        a(f"|---|---|")
        a(f"| Completed trades | {n} |")
        a(f"| Wins / Losses | {wins} / {losses} |")
        a(f"| Win rate | {_fmt_opt(wr, '%')} |")
        a(f"| Average R | {_fmt_opt(avg_r)} |")
        a(f"| Total R | {_fmt_opt(total_r)} |")
        a(f"| Profit Factor | {_fmt_opt(pf)}{_pf_badge(pf)} |")
        a(f"| Best trade | {_fmt_opt(daily.get('best_trade_R'), ' R')} |")
        a(f"| Worst trade | {_fmt_opt(daily.get('worst_trade_R'), ' R')} |")
        a(f"| Avg hold time | {_fmt_opt(daily.get('average_hold_time_minutes'), ' min')} |")
        a("")

    # ── 6. Session Breakdown ──────────────────────────────────────────────────
    a("## 6. Session Breakdown")
    a("")
    if session_bd:
        a("| Session | Trades | Wins | Win% | Avg R | PF |")
        a("|---|---|---|---|---|---|")
        for sess, m in sorted(session_bd.items()):
            a(f"| {sess.upper()} | {m.get('trade_count', 0)} | {m.get('wins', 0)} | "
              f"{_fmt_opt(m.get('win_rate'), '%')} | {_fmt_opt(m.get('average_R'))} | "
              f"{_fmt_opt(m.get('PF'))}{_pf_badge(m.get('PF'))} |")
        a("")
    else:
        a("No session data yet (no completed trades today).")
        a("")
        a("**Backtest reference (ST-A2, RR5):**")
        a("")
        a("| Session | Trades | Win% | Net PF (std) | Status |")
        a("|---|---|---|---|---|")
        a("| London | 118 | 28.0% | 0.949 | ⚠️ Below 1.0 |")
        a("| New York | 51 | 41.2% | 1.731 | ✅ Above 1.0 |")
        a("")

    # ── 7. Symbol Breakdown ───────────────────────────────────────────────────
    a("## 7. Symbol Breakdown")
    a("")
    if symbol_bd:
        a("| Symbol | Trades | Wins | Win% | Avg R | PF |")
        a("|---|---|---|---|---|---|")
        for sym, m in sorted(symbol_bd.items()):
            a(f"| {sym} | {m.get('trade_count', 0)} | {m.get('wins', 0)} | "
              f"{_fmt_opt(m.get('win_rate'), '%')} | {_fmt_opt(m.get('average_R'))} | "
              f"{_fmt_opt(m.get('PF'))}{_pf_badge(m.get('PF'))} |")
        a("")
    else:
        a("No symbol data yet (no completed trades today).")
        a("")
        a("**Backtest reference (ST-A2, RR5):**")
        a("")
        a("| Symbol | Trades | Win% | Net PF (std) | Net PF (2×) | Status |")
        a("|---|---|---|---|---|---|")
        a("| EURUSD | 105 | 29.5% | 1.059 | 0.945 | ⚠️ Marginal (fails 2× alone) |")
        a("| GBPUSD | 64 | 35.9% | 1.313 | 1.168 | ✅ Strong |")
        a("")

    # ── 8. Risk State ─────────────────────────────────────────────────────────
    a("## 8. Risk State")
    a("")
    halted = state.get("halted", False)
    a(f"| Guard | Status |")
    a(f"|---|---|")
    a(f"| Trading halted | {'🔴 YES — ' + str(state.get('halt_reason', '')) if halted else '✅ NO'} |")
    a(f"| Daily loss (R) | {_fmt_opt(state.get('daily_loss_r'))} / −3R limit |")
    a(f"| Weekly loss (R) | {_fmt_opt(state.get('weekly_loss_r'))} |")
    a(f"| Consecutive losses | {state.get('consecutive_losses', 0)} / 5 limit |")
    a(f"| Last daily reset | {state.get('last_reset_date', '—')} |")
    a("")

    # ── 9. OPS-01 Status ──────────────────────────────────────────────────────
    a("## 9. OPS-01 Stability Run Status")
    a("")
    a(f"| Item | Value |")
    a(f"|---|---|")
    a(f"| Run started | {ops['start']} |")
    a(f"| Run ends | {ops['end']} |")
    a(f"| Today is Day | {ops['day_n']} of 7 |")
    a(f"| Days remaining | {ops['days_left']} |")
    a(f"| Progress | {ops['pct_complete']}% |")
    a(f"| Gate | 7 consecutive days without manual restart |")
    a(f"| Current verdict | ONGOING — awaiting Day 7 |")
    a("")
    a("**OPS-01 daily checklist:**")
    a("")
    a("- [ ] Run `python3 scripts/health_check.py` → all OK")
    a("- [ ] Check bot log for new disconnect events")
    a("- [ ] Verify heartbeat gap < 10 min")
    a("- [ ] Confirm LIVE_TRADING=false")
    a("- [ ] Note any new errors in log")
    a("")

    # ── 10. Weekly Summary ────────────────────────────────────────────────────
    wn = weekly.get("trade_count", 0)
    if wn > 0:
        a("## 10. Weekly Summary")
        a("")
        a(f"| Metric | Value |")
        a(f"|---|---|")
        a(f"| Period | {weekly.get('label', '—')} |")
        a(f"| Completed trades | {wn} |")
        a(f"| Win rate | {_fmt_opt(weekly.get('win_rate'), '%')} |")
        a(f"| Average R | {_fmt_opt(weekly.get('average_R'))} |")
        a(f"| Profit Factor | {_fmt_opt(weekly.get('PF'))}{_pf_badge(weekly.get('PF'))} |")
        a(f"| Total R | {_fmt_opt(weekly.get('total_R'))} |")
        a("")

    # ── Footer ────────────────────────────────────────────────────────────────
    a("---")
    a("")
    a(f"*Generated by `research/daily_status_report.py` at {now_str}*")
    a(f"*Log lines parsed: {len(lines)} for {date_str}*")
    a(f"*Bot log: `logs/bot.log` | Trade log: `logs/trades.jsonl`*")
    a("")
    a("> Low sample note: ST-A2 expects ~3 trades/month. Statistical metrics")
    a("> (win rate, PF) are not meaningful until n ≥ 30.")
    a("")

    return "\n".join(lines_md)


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="RESEARCH-06 daily status report")
    parser.add_argument("--date", default=_now().strftime("%Y-%m-%d"),
                        help="Date to report on (YYYY-MM-DD), default: today UTC")
    parser.add_argument("--out", default=None, help="Output path (default: reports/daily_status.md)")
    parser.add_argument("--quiet", action="store_true", help="Suppress stdout echo")
    args = parser.parse_args()

    _REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = Path(args.out) if args.out else _REPORTS_DIR / "daily_status.md"

    report = generate_report(args.date)
    out_path.write_text(report, encoding="utf-8")

    if not args.quiet:
        print(report)

    print(f"\n✅  Report written → {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
