from __future__ import annotations

from strategy_audit.audit_engine import StrategyAuditEngine
from strategy_audit.audit_runner import StrategyAuditRunner
from strategy_audit.models import AuditContext


def _strategy_text() -> str:
    return """
Market: FX
Session: London and New York
Bias: Bullish
Entry Trigger: Sweep then CHOCH
Confirmation: FVG and Order Block
Invalidation: If price closes back below the swept low
Stop Loss: Below sweep
Take Profit: 2R
Risk: 0.3%
Filters: HTF bias, session filter, spread filter
Exit Rules: Close at target, no trailing stop
""".strip()


def _candles() -> list[dict[str, object]]:
    return [
        {
            "time": "2026-06-01T08:00:00Z",
            "open": 1.10,
            "high": 1.11,
            "low": 1.09,
            "close": 1.105,
        },
        {
            "time": "2026-06-01T08:15:00Z",
            "open": 1.105,
            "high": 1.115,
            "low": 1.10,
            "close": 1.112,
        },
        {
            "time": "2026-06-01T08:30:00Z",
            "open": 1.112,
            "high": 1.12,
            "low": 1.11,
            "close": 1.118,
        },
    ]


def _trades() -> list[dict[str, object]]:
    returns = [0.4, 0.6, 0.2, 0.8, 0.3, 0.7, 0.1, 0.5, 0.9, 0.2, 0.4, 0.6]
    trades = []
    for idx, value in enumerate(returns, start=1):
        trades.append(
            {
                "trade_id": f"T{idx}",
                "timestamp": f"2026-06-01T08:{idx:02d}:00Z",
                "session": "London" if idx % 2 else "New York",
                "regime": "trending" if idx % 3 else "ranging",
                "std_net_r": value,
                "net_r": value,
            }
        )
    return trades


def _execution_report() -> dict[str, object]:
    return {
        "status": "READY FOR DEMO",
        "readiness_status": "READY_FOR_DEMO",
        "final_score": 100,
        "broker_simulation_passed": True,
        "recovery_passed": True,
        "strategy_version_control_passed": True,
        "slippage_average_pip": 0.2,
        "slippage_p95_pip": 0.3,
        "execution_delay_ms_average": 180,
        "execution_delay_ms_maximum": 250,
    }


def test_full_audit_report_generates(tmp_path):
    context = AuditContext(
        strategy_name="ST-A2",
        strategy_text=_strategy_text(),
        candles=_candles(),
        trades=_trades(),
        execution_report=_execution_report(),
        historical_metrics={
            "profit_factor": 1.45,
            "win_rate": 0.54,
            "expectancy": 0.42,
            "max_drawdown": 3.8,
        },
        live_metrics={
            "profit_factor": 1.42,
            "win_rate": 0.53,
            "expectancy": 0.41,
            "max_drawdown": 3.9,
        },
        parameter_grid={"best_profit_factor": 1.6, "runner_up_profit_factor": 1.25},
        notes={
            "risk": {
                "daily_dd_pct": 1.5,
                "weekly_dd_pct": 3.0,
                "monthly_dd_pct": 5.5,
                "portfolio_heat_pct": 0.5,
            },
            "risk_limits": {"daily_dd_pct": 2.0},
            "capital_allocation": {"tier": "Demo"},
            "monitoring": {"alerts": 3},
            "health_checks": {"broker": True, "logger": True},
            "spread_samples": [{"spread_pips": 0.4}, {"spread_pips": 0.6}],
            "signals": [{"signal_id": "S1"}],
        },
    )

    engine = StrategyAuditEngine()
    report = engine.audit(context)

    assert report.readiness_score > 80
    assert report.deployment_status in {"Demo", "Pilot Live", "Production"}
    assert any(module.name == "rule_audit" for module in report.module_results)

    runner = StrategyAuditRunner(engine=engine, output_dir=tmp_path)
    written = runner.run(context)
    assert (tmp_path / "ST-A2" / "audit_report.json").exists()
    assert (tmp_path / "ST-A2" / "audit_report.pdf").read_bytes().startswith(b"%PDF")
    assert written.strategy == "ST-A2"


def test_audit_runner_from_payload(tmp_path):
    payload = {
        "strategy_name": "ST-A2",
        "strategy_text": _strategy_text(),
        "candles": _candles(),
        "trades": _trades(),
        "execution_report": _execution_report(),
        "historical_metrics": {
            "profit_factor": 1.45,
            "win_rate": 0.54,
            "expectancy": 0.42,
            "max_drawdown": 3.8,
        },
        "live_metrics": {
            "profit_factor": 1.42,
            "win_rate": 0.53,
            "expectancy": 0.41,
            "max_drawdown": 3.9,
        },
        "parameter_grid": {"best_profit_factor": 1.6, "runner_up_profit_factor": 1.25},
        "notes": {
            "risk": {
                "daily_dd_pct": 1.5,
                "weekly_dd_pct": 3.0,
                "monthly_dd_pct": 5.5,
                "portfolio_heat_pct": 0.5,
            }
        },
    }
    payload_path = tmp_path / "payload.json"
    payload_path.write_text(__import__("json").dumps(payload), encoding="utf-8")

    runner = StrategyAuditRunner(output_dir=tmp_path)
    report = runner.from_payload(payload)
    assert report.overall_status in {"PASS", "PARTIAL"}
