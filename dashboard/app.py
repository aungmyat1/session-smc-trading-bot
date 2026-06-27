#!/usr/bin/env python3
"""
SVOS / EVF / Trade Status — Dashboard API server.

Serves:
  GET /api/svos          — SVOS panel data (strategy catalog + last run)
  GET /api/evf           — EVF panel data (last validation report)
  GET /api/trades        — Live trade status (journal + open positions)
  GET /api/status        — System health summary
  POST /api/svos/run     — Trigger SVOS run (confirm token required)
  POST /api/evf/run      — Trigger EVF run  (confirm token required)

Run:
  pip install flask pyyaml
  python dashboard/app.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

try:
    from flask import Flask, jsonify, request, send_from_directory
    from flask_cors import CORS
except ImportError:
    print("Flask not installed. Run: pip install flask flask-cors")
    sys.exit(1)

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]

app = Flask(__name__, static_folder=str(Path(__file__).parent / "static"))
CORS(app)

_CATALOG_PATH = _ROOT / "config" / "strategy_catalog.yaml"
_EVF_REPORTS_DIR = _ROOT / "execution_validation" / "reports"
_JOURNAL_PATHS = [
    _ROOT / "logs" / "trades.jsonl",
    _ROOT / "logs" / "adaptive_trades.jsonl",
]
_SVOS_REPORTS_DIR = _ROOT / "reports" / "current_strategy_svos"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_yaml(path: Path) -> dict[str, Any]:
    if yaml is None or not path.exists():
        return {}
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _read_jsonl(path: Path, limit: int = 200) -> list[dict]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    records = []
    for line in lines[-limit:]:
        line = line.strip()
        if line:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return records


def _latest_evf_report() -> dict[str, Any]:
    """Return the most-recent EVF JSON report or empty dict."""
    if not _EVF_REPORTS_DIR.exists():
        return {}
    candidates = sorted(_EVF_REPORTS_DIR.glob("**/*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for path in candidates:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
    return {}


def _latest_svos_report(strategy: str) -> dict[str, Any]:
    strategy_dir = _SVOS_REPORTS_DIR / strategy
    if not strategy_dir.exists():
        return {}
    candidates = sorted(strategy_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for path in candidates:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
    return {}


def _all_trades() -> list[dict]:
    records = []
    for path in _JOURNAL_PATHS:
        records.extend(_read_jsonl(path))
    records.sort(key=lambda r: r.get("timestamp", ""), reverse=True)
    return records


def _trade_stats(records: list[dict]) -> dict[str, Any]:
    closed = [r for r in records if r.get("record_type") != "signal" and r.get("result_r") is not None]
    if not closed:
        return {"total": 0, "wins": 0, "losses": 0, "win_rate": 0.0, "avg_r": 0.0, "total_r": 0.0}
    wins = [r for r in closed if (r.get("result_r") or 0) > 0]
    losses = [r for r in closed if (r.get("result_r") or 0) <= 0]
    total_r = sum(r.get("result_r", 0) for r in closed)
    avg_r = total_r / len(closed)
    win_rate = len(wins) / len(closed) * 100 if closed else 0
    return {
        "total": len(closed),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(win_rate, 1),
        "avg_r": round(avg_r, 3),
        "total_r": round(total_r, 3),
    }

# ---------------------------------------------------------------------------
# SVOS API
# ---------------------------------------------------------------------------

@app.route("/api/svos")
def api_svos():
    catalog = _read_yaml(_CATALOG_PATH)
    strategies = catalog.get("strategies", {})
    current = catalog.get("current_strategy", "")

    strategy_list = []
    for name, meta in strategies.items():
        if not isinstance(meta, dict):
            meta = {}
        strategy_list.append({
            "name": name,
            "status": meta.get("status", "unknown"),
            "version": meta.get("version", ""),
            "approved": meta.get("approved", False),
            "current": meta.get("current", False),
            "description": meta.get("description", ""),
            "symbols": meta.get("symbols", []),
            "timeframes": meta.get("timeframes", []),
            "requirements": meta.get("requirements", {}),
            "last_svos_at": meta.get("last_svos_at", ""),
            "last_svos_status": meta.get("last_svos_status", ""),
            "last_svos_promoted_stage": meta.get("last_svos_promoted_stage", ""),
        })

    current_report = _latest_svos_report(current) if current else {}

    return jsonify({
        "current_strategy": current,
        "strategies": strategy_list,
        "current_report": current_report,
        "fetched_at": _now_iso(),
    })


@app.route("/api/svos/run", methods=["POST"])
def api_svos_run():
    body = request.get_json(silent=True) or {}
    confirm = body.get("confirm_token", "")
    strategy = body.get("strategy", "")
    if confirm != f"CONFIRM-SVOS-{strategy}":
        return jsonify({"error": "Invalid or missing CONFIRM token", "required": f"CONFIRM-SVOS-{strategy}"}), 403

    cmd = [sys.executable, str(_ROOT / "scripts" / "run_current_strategy_svos.py"), "--strategy", strategy]
    try:
        proc = subprocess.Popen(cmd, cwd=str(_ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        out, _ = proc.communicate(timeout=120)
        return jsonify({"status": "completed", "returncode": proc.returncode, "output": out[-4000:]})
    except subprocess.TimeoutExpired:
        proc.kill()
        return jsonify({"status": "timeout"}), 408
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

# ---------------------------------------------------------------------------
# EVF API
# ---------------------------------------------------------------------------

@app.route("/api/evf")
def api_evf():
    report = _latest_evf_report()
    checks = report.get("checks", {})
    check_list = [
        {"name": k, "passed": v.get("passed", False), "message": v.get("message", ""), "score": v.get("score", 0)}
        for k, v in checks.items()
    ] if isinstance(checks, dict) else []

    return jsonify({
        "strategy": report.get("strategy", ""),
        "period": report.get("period", ""),
        "status": report.get("status", "UNKNOWN"),
        "final_score": report.get("final_score", 0),
        "created_at": report.get("created_at", ""),
        "signal_accuracy": report.get("signal_accuracy", 0),
        "order_accuracy": report.get("order_accuracy", 0),
        "risk_accuracy": report.get("risk_accuracy", 0),
        "slippage_average_pip": report.get("slippage_average_pip", 0),
        "slippage_p95_pip": report.get("slippage_p95_pip", 0),
        "execution_delay_ms_average": report.get("execution_delay_ms_average", 0),
        "duplicate_order_protection_passed": report.get("duplicate_order_protection_passed", False),
        "spread_handling_passed": report.get("spread_handling_passed", False),
        "slippage_passed": report.get("slippage_passed", False),
        "exit_management_passed": report.get("exit_management_passed", False),
        "recovery_passed": report.get("recovery_passed", False),
        "broker_simulation_passed": report.get("broker_simulation_passed", False),
        "checks": check_list,
        "fetched_at": _now_iso(),
    })


@app.route("/api/evf/run", methods=["POST"])
def api_evf_run():
    body = request.get_json(silent=True) or {}
    confirm = body.get("confirm_token", "")
    strategy = body.get("strategy", "")
    payload_path = body.get("payload_path", "")
    if confirm != f"CONFIRM-EVF-{strategy}":
        return jsonify({"error": "Invalid or missing CONFIRM token", "required": f"CONFIRM-EVF-{strategy}"}), 403

    cmd = [sys.executable, str(_ROOT / "scripts" / "run_evf.py"), "--strategy", strategy]
    if payload_path:
        cmd += ["--payload", payload_path]
    try:
        proc = subprocess.Popen(cmd, cwd=str(_ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        out, _ = proc.communicate(timeout=120)
        return jsonify({"status": "completed", "returncode": proc.returncode, "output": out[-4000:]})
    except subprocess.TimeoutExpired:
        proc.kill()
        return jsonify({"status": "timeout"}), 408
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

# ---------------------------------------------------------------------------
# Trade status API
# ---------------------------------------------------------------------------

@app.route("/api/trades")
def api_trades():
    records = _all_trades()
    stats = _trade_stats(records)
    recent = records[:50]
    return jsonify({
        "stats": stats,
        "recent": recent,
        "fetched_at": _now_iso(),
    })


@app.route("/api/status")
def api_status():
    catalog = _read_yaml(_CATALOG_PATH)
    strategies = catalog.get("strategies", {})
    current = catalog.get("current_strategy", "")
    current_meta = strategies.get(current, {})

    records = _all_trades()
    stats = _trade_stats(records)
    evf = _latest_evf_report()

    return jsonify({
        "system": "ONLINE",
        "current_strategy": current,
        "strategy_status": current_meta.get("status", "unknown"),
        "strategy_approved": current_meta.get("approved", False),
        "last_svos_status": current_meta.get("last_svos_status", ""),
        "last_svos_at": current_meta.get("last_svos_at", ""),
        "evf_status": evf.get("status", "NO REPORT"),
        "evf_score": evf.get("final_score", 0),
        "trade_count": stats["total"],
        "win_rate": stats["win_rate"],
        "live_trading": os.getenv("LIVE_TRADING", "false").lower() == "true",
        "fetched_at": _now_iso(),
    })

# ---------------------------------------------------------------------------
# Static dashboard
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return send_from_directory(str(Path(__file__).parent), "index.html")


if __name__ == "__main__":
    port = int(os.getenv("DASHBOARD_PORT", "8080"))
    print(f"Dashboard running at http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
