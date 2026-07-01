from __future__ import annotations

import json

from agtrade.cli import main


def test_agtrade_research_status_summarizes_queue(tmp_path, capsys):
    queue_path = tmp_path / "research_queue.yaml"
    queue_path.write_text(
        """
jobs:
  - job_id: job-1
    strategy: ST-A2
    enabled: true
    steps:
      - name: replay
        command: ["python", "scripts/replay_2025.py"]
      - name: approval
        blocked: true
        reason: waiting for governance
  - job_id: job-2
    strategy: D2E3
    enabled: false
    steps:
      - name: backtest
        command: ["python", "scripts/backtest.py"]
""".strip()
        + "\n",
        encoding="utf-8",
    )

    exit_code = main(["research", "status", "--queue", str(queue_path)])
    captured = capsys.readouterr()

    assert exit_code == 0
    payload = json.loads(captured.out)
    assert payload["job_count"] == 2
    assert payload["enabled_job_count"] == 1
    assert payload["blocked_step_count"] == 1


def test_agtrade_strategy_audit_routes_to_existing_audit_cli(tmp_path, capsys):
    payload = {
        "strategy_text": """
Market: FX
Session: London
Bias: Bullish
Entry Trigger: Sweep
Confirmation: FVG
Invalidation: If price closes back below the sweep
Stop Loss: Below sweep
Take Profit: 2R
Risk: 0.3%
Filters: Session filter
Exit Rules: Close at target
""".strip(),
        "candles": [{"time": "2026-06-01T08:00:00Z", "open": 1, "high": 2, "low": 0.5, "close": 1.5}],
        "trades": [{"trade_id": "T1", "timestamp": "2026-06-01T08:15:00Z", "std_net_r": 0.5, "session": "London", "regime": "trending"}],
        "execution_report": {
            "status": "READY FOR DEMO",
            "readiness_status": "READY_FOR_DEMO",
            "final_score": 100,
            "broker_simulation_passed": True,
            "recovery_passed": True,
            "strategy_version_control_passed": True,
        },
        "historical_metrics": {"profit_factor": 1.45, "win_rate": 0.54, "expectancy": 0.42, "max_drawdown": 3.8},
        "live_metrics": {"profit_factor": 1.42, "win_rate": 0.53, "expectancy": 0.41, "max_drawdown": 3.9},
        "parameter_grid": {"best_profit_factor": 1.6, "runner_up_profit_factor": 1.25},
        "notes": {"risk": {"daily_dd_pct": 1.5, "weekly_dd_pct": 3.0, "monthly_dd_pct": 5.5, "portfolio_heat_pct": 0.5}},
    }
    payload_path = tmp_path / "payload.json"
    payload_path.write_text(json.dumps(payload), encoding="utf-8")

    exit_code = main(["strategy", "audit", "--strategy", "ST-A2", "--payload", str(payload_path), "--outdir", str(tmp_path / "reports")])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "ST-A2" in captured.out
