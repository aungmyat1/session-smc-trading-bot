#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

try:
    from flask import Flask, jsonify, request, send_from_directory
    from flask_cors import CORS
except ImportError:
    print("Flask not installed. Run: pip install flask flask-cors")
    sys.exit(1)

from dashboard.audit_log import write_audit_log
from dashboard.auth import require_operator
from dashboard import live_dashboard_service
from dashboard.runtime import (
    dashboard_url,
    live_dashboard_bind_host,
    live_dashboard_port,
    live_dashboard_public_host,
)

app = Flask(__name__, static_folder=str(Path(__file__).parent))
_allowed_origins = [
    item.strip()
    for item in os.getenv(
        "LIVE_DASHBOARD_ALLOWED_ORIGINS",
        "http://127.0.0.1:8090,http://localhost:8090",
    ).split(",")
    if item.strip()
]
CORS(app, resources={r"/api/*": {"origins": _allowed_origins}})

_LIVE_DASHBOARD_HTML = Path(__file__).parent / "live_dashboard.html"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@app.route("/")
@app.route("/live-dashboard")
@app.route("/live-dashboard/")
def index():
    return send_from_directory(str(Path(__file__).parent), _LIVE_DASHBOARD_HTML.name)


@app.route("/api/live-dashboard")
def api_live_dashboard():
    chart_symbol = str(request.args.get("symbol", "")).strip() or None
    timeframe = str(request.args.get("timeframe", "M15")).strip() or "M15"
    count = request.args.get("count", default=120, type=int) or 120
    return jsonify(
        live_dashboard_service.load_snapshot(
            chart_symbol=chart_symbol,
            timeframe=timeframe,
            candle_count=max(10, min(count, 500)),
        )
    )


@app.route("/api/live-dashboard/positions/<position_id>/close", methods=["POST"])
@require_operator(app, "risk_operator", "admin")
def api_live_dashboard_close_position(position_id: str):
    try:
        payload = live_dashboard_service.close_position(position_id)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 502
    write_audit_log(
        "live_dashboard_close_position",
        status="completed" if payload.get("ok") else "failed",
        detail={**payload, "actor": request.environ["svos.actor"]},
    )
    return jsonify({**payload, "fetched_at": _now_iso()})


@app.route("/api/live-dashboard/positions/<position_id>/protect", methods=["POST"])
@require_operator(app, "risk_operator", "admin")
def api_live_dashboard_modify_position(position_id: str):
    body = request.get_json(silent=True) or {}
    stop_loss = body.get("stop_loss")
    take_profit = body.get("take_profit")
    if stop_loss in (None, "") or take_profit in (None, ""):
        return jsonify({"error": "stop_loss and take_profit are required"}), 400
    try:
        payload = live_dashboard_service.modify_position(position_id, float(stop_loss), float(take_profit))
    except ValueError:
        return jsonify({"error": "stop_loss and take_profit must be numeric"}), 400
    except Exception as exc:
        return jsonify({"error": str(exc)}), 502
    write_audit_log(
        "live_dashboard_modify_position",
        status="completed" if payload.get("ok") else "failed",
        detail={**payload, "actor": request.environ["svos.actor"]},
    )
    return jsonify({**payload, "fetched_at": _now_iso()})


@app.route("/api/live-dashboard/orders/<order_id>/cancel", methods=["POST"])
@require_operator(app, "risk_operator", "admin")
def api_live_dashboard_cancel_order(order_id: str):
    try:
        payload = live_dashboard_service.cancel_order(order_id)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 502
    write_audit_log(
        "live_dashboard_cancel_order",
        status="completed" if payload.get("ok") else "failed",
        detail={**payload, "actor": request.environ["svos.actor"]},
    )
    return jsonify({**payload, "fetched_at": _now_iso()})


@app.route("/health")
def health():
    public_host = live_dashboard_public_host(live_dashboard_bind_host())
    port = live_dashboard_port()
    return jsonify(
        {
            "status": "ok",
            "service": "live_dashboard",
            "url": dashboard_url(public_host, port),
            "fetched_at": _now_iso(),
        }
    )


if __name__ == "__main__":
    port = live_dashboard_port()
    bind_host = live_dashboard_bind_host()
    public_host = live_dashboard_public_host(bind_host)
    print(f"Live dashboard running at {dashboard_url(public_host, port)} (bind={bind_host})")
    app.run(host=bind_host, port=port, debug=False)
