import json
from pathlib import Path

from research.svos.engine import (
    DemoValidationInput,
    RobustnessValidationInput,
    SVOSRunner,
    StrategyAuditEngine,
    StrategyIntakeEngine,
    audit_strategy_text,
)
from research.validation.engine import BacktestValidationInput, ReplayTrade, ReplayValidationInput


def _complete_strategy_text() -> str:
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


def _valid_replay() -> ReplayValidationInput:
    return ReplayValidationInput(
        completed_successfully=True,
        trades=[
            ReplayTrade(
                trade_id="T1",
                timestamp="2026-06-01T08:00:00Z",
                side="long",
                entry_price=1.1000,
                stop_loss=1.0950,
                take_profit=1.1100,
                position_size=0.10,
                required_features=["sweep", "bias"],
            )
        ],
        state_transitions=[("IDLE", "SETUP"), ("SETUP", "CONFIRMED"), ("CONFIRMED", "ORDER_PLACED"), ("ORDER_PLACED", "FILLED"), ("FILLED", "CLOSED")],
        required_features=["sweep", "bias"],
        available_features=["sweep", "bias"],
    )


def _valid_backtest() -> BacktestValidationInput:
    return BacktestValidationInput(
        completed_successfully=True,
        trade_count=120,
        expectancy=0.12,
        max_drawdown=4.5,
        profit_factor=1.25,
        metrics={
            "trade_count": 120,
            "expectancy": 0.12,
            "max_drawdown": 4.5,
            "profit_factor": 1.25,
            "win_rate": 0.35,
            "net_return": 12.0,
        },
    )


def _valid_execution_report() -> dict[str, object]:
    return {
        "status": "READY FOR DEMO",
        "readiness_status": "READY_FOR_DEMO",
        "final_score": 100,
        "broker_simulation_passed": True,
        "recovery_passed": True,
        "strategy_version_control_passed": True,
    }


def test_audit_requires_complete_spec():
    result = audit_strategy_text("London Session\nLiquidity Sweep\nRR 1:2\nRisk 0.3%")
    assert result.status == "FIX"
    assert result.spec is not None
    assert "stop_loss" in result.spec.missing_fields
    assert result.clarifying_questions


def test_audit_detects_contradiction():
    text = """
    Market: FX
    Session: London
    Bias: Long and Short
    Entry Trigger: Sweep
    Confirmation: FVG
    Invalidation: If price returns
    Stop Loss: Below sweep
    Take Profit: 2R
    Risk: 0.3%
    Filters: HTF bias
    Exit Rules: Close at target
    """
    result = StrategyAuditEngine().audit(text, strategy_name="TEST")
    assert result.status == "FAIL"
    assert any(issue.code.startswith("contradictory") for issue in result.issues)


def test_audit_flags_missing_data_dependencies():
    strategy = {
        "text": _complete_strategy_text(),
        "required_data": ["order_book", "volume_profile"],
        "available_data": ["ohlc"],
    }
    result = StrategyAuditEngine().audit(strategy, strategy_name="TEST")
    assert result.status == "FAIL"
    assert any(issue.code == "missing_data" for issue in result.issues)
    assert result.metadata["data_availability"]["status"] == "MISSING"


def test_audit_warns_on_many_fixed_parameters():
    text = """
    Market: FX
    Session: London
    Bias: Bullish
    Entry Trigger: Sweep
    Confirmation: FVG
    Invalidation: If price closes back below the sweep
    Stop Loss: 18 pips
    Take Profit: 36 pips
    Risk: 0.3%
    Filters: EMA 20, EMA 21, EMA 22, RSI 43, ATR 2.3, Stop 18, Target 36, Lookback 15
    Exit Rules: Close at target and scale out at 1.5R
    """
    result = StrategyAuditEngine().audit(text, strategy_name="TEST")
    assert result.status == "FIX"
    assert any(issue.code == "possible_overfitting" for issue in result.issues)


def test_intake_creates_canonical_strategy_record():
    result = StrategyIntakeEngine().intake(_complete_strategy_text(), strategy_name="TEST")
    assert result.status == "PASS"
    assert result.metadata["strategy_name"] == "TEST"
    assert result.metadata["version_history_initialized"] is True
    assert result.metadata["canonical_spec"]["fields"]["market"] == "FX"


def test_runner_passes_all_stages_and_promotes(tmp_path):
    catalog_copy = tmp_path / "strategy_catalog.yaml"
    catalog_copy.write_text(Path("config/strategy_catalog.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    runner = SVOSRunner("ST-A2", registry_path=catalog_copy, output_dir=tmp_path)
    result = runner.run_pipeline(
        _complete_strategy_text(),
        replay=_valid_replay(),
        backtest=_valid_backtest(),
        robustness=RobustnessValidationInput(
            completed_successfully=True,
            walk_forward_passed=True,
            monte_carlo_passed=True,
            parameter_stability_passed=True,
            regime_analysis_passed=True,
            execution_cost_passed=True,
            latest_metrics={
                "profit_factor": 1.22,
                "win_rate": 0.36,
                "expectancy": 0.11,
                "max_drawdown": 4.8,
            },
            previous_metrics={
                "profit_factor": 1.20,
                "win_rate": 0.35,
                "expectancy": 0.10,
                "max_drawdown": 4.7,
            },
        ),
        demo=DemoValidationInput(
            completed_successfully=True,
            days_monitored=20,
            min_demo_days=14,
            tolerance_pct=0.10,
            research_metrics={
                "profit_factor": 1.20,
                "win_rate": 0.35,
                "expectancy": 0.10,
                "max_drawdown": 4.7,
            },
            live_metrics={
                "profit_factor": 1.18,
                "win_rate": 0.34,
                "expectancy": 0.099,
                "max_drawdown": 4.9,
            },
            execution_validation_report=_valid_execution_report(),
        ),
        promote=True,
        allow_live_promotion=True,
    )
    assert result.overall_status == "PASS"
    assert any(stage.stage == "verification_ready" and stage.status == "PASS" for stage in result.stages)
    assert result.stages[-2].stage == "virtual_demo"
    assert result.stages[-1].stage == "production_approval"
    assert result.stages[-1].status == "PASS"
    assert result.promoted_stage == "live"
    assert Path(tmp_path / "ST-A2" / "svos_result.json").exists()
    stage_dir = tmp_path / "ST-A2" / "stages"
    expected_stage_files = [
        "00_intake",
        "01_audit",
        "02_enhancement",
        "03_replay",
        "04_backtest",
        "05_robustness",
        "06_verification_ready",
        "07_virtual_demo",
        "08_production_approval",
    ]
    for stem in expected_stage_files:
        assert (stage_dir / f"{stem}.json").exists()
        assert (stage_dir / f"{stem}.md").exists()
    index = json.loads((stage_dir / "index.json").read_text(encoding="utf-8"))
    assert index["overall_status"] == "PASS"
    assert index["promoted_stage"] == "live"
    production_report = json.loads((stage_dir / "08_production_approval.json").read_text(encoding="utf-8"))
    assert production_report["current_stage"]["stage"] == "production_approval"
    assert production_report["promoted_stage"] == "live"
    assert get_strategy_status(catalog_copy, "ST-A2") == "live"


def test_runner_can_stop_at_verification_ready(tmp_path):
    catalog_copy = tmp_path / "strategy_catalog.yaml"
    catalog_copy.write_text(Path("config/strategy_catalog.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    runner = SVOSRunner("ST-A2", registry_path=catalog_copy, output_dir=tmp_path)
    result = runner.run_pipeline(
        _complete_strategy_text(),
        replay=_valid_replay(),
        backtest=_valid_backtest(),
        robustness=RobustnessValidationInput(
            completed_successfully=True,
            walk_forward_passed=True,
            monte_carlo_passed=True,
            parameter_stability_passed=True,
            regime_analysis_passed=True,
            execution_cost_passed=True,
            latest_metrics={
                "profit_factor": 1.22,
                "win_rate": 0.36,
                "expectancy": 0.11,
                "max_drawdown": 4.8,
            },
            previous_metrics={
                "profit_factor": 1.20,
                "win_rate": 0.35,
                "expectancy": 0.10,
                "max_drawdown": 4.7,
            },
        ),
        stop_after="verification_ready",
    )
    assert result.overall_status == "PASS"
    assert result.stages[-1].stage == "verification_ready"
    assert all(stage.stage != "virtual_demo" for stage in result.stages)
    verification_stage = result.stages[-1]
    assert verification_stage.metadata["verification_ready"] is True
    assert verification_stage.next_stage == "virtual_demo"


def test_runner_returns_fix_when_demo_metrics_missing(tmp_path):
    catalog_copy = tmp_path / "strategy_catalog.yaml"
    catalog_copy.write_text(Path("config/strategy_catalog.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    runner = SVOSRunner("ST-A2", registry_path=catalog_copy, output_dir=tmp_path)
    result = runner.run_pipeline(
        _complete_strategy_text(),
        replay=_valid_replay(),
        backtest=_valid_backtest(),
        robustness=RobustnessValidationInput(
            completed_successfully=True,
            walk_forward_passed=True,
            monte_carlo_passed=True,
            parameter_stability_passed=True,
            regime_analysis_passed=True,
            execution_cost_passed=True,
            latest_metrics={
                "profit_factor": 1.22,
                "win_rate": 0.36,
                "expectancy": 0.11,
                "max_drawdown": 4.8,
            },
            previous_metrics={
                "profit_factor": 1.20,
                "win_rate": 0.35,
                "expectancy": 0.10,
                "max_drawdown": 4.7,
            },
        ),
        demo=DemoValidationInput(
            completed_successfully=True,
            days_monitored=5,
            min_demo_days=14,
            tolerance_pct=0.10,
            research_metrics={
                "profit_factor": 1.20,
                "win_rate": 0.35,
                "expectancy": 0.10,
                "max_drawdown": 4.7,
            },
            live_metrics={
                "profit_factor": 1.18,
                "win_rate": 0.34,
                "expectancy": 0.099,
                "max_drawdown": 4.9,
            },
            execution_validation_report=_valid_execution_report(),
        ),
    )
    assert result.overall_status == "FAIL"
    assert any(stage.stage == "virtual_demo" and stage.status == "FAIL" for stage in result.stages)
    assert get_strategy_status(catalog_copy, "ST-A2") != "live"


def test_runner_does_not_promote_to_live_without_explicit_allow(tmp_path):
    catalog_copy = tmp_path / "strategy_catalog.yaml"
    catalog_copy.write_text(Path("config/strategy_catalog.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    runner = SVOSRunner("ST-A2", registry_path=catalog_copy, output_dir=tmp_path)
    result = runner.run_pipeline(
        _complete_strategy_text(),
        replay=_valid_replay(),
        backtest=_valid_backtest(),
        robustness=RobustnessValidationInput(
            completed_successfully=True,
            walk_forward_passed=True,
            monte_carlo_passed=True,
            parameter_stability_passed=True,
            regime_analysis_passed=True,
            execution_cost_passed=True,
            latest_metrics={
                "profit_factor": 1.22,
                "win_rate": 0.36,
                "expectancy": 0.11,
                "max_drawdown": 4.8,
            },
            previous_metrics={
                "profit_factor": 1.20,
                "win_rate": 0.35,
                "expectancy": 0.10,
                "max_drawdown": 4.7,
            },
        ),
        demo=DemoValidationInput(
            completed_successfully=True,
            days_monitored=20,
            min_demo_days=14,
            tolerance_pct=0.10,
            research_metrics={
                "profit_factor": 1.20,
                "win_rate": 0.35,
                "expectancy": 0.10,
                "max_drawdown": 4.7,
            },
            live_metrics={
                "profit_factor": 1.18,
                "win_rate": 0.34,
                "expectancy": 0.099,
                "max_drawdown": 4.9,
            },
            execution_validation_report=_valid_execution_report(),
        ),
        promote=True,
        allow_live_promotion=False,
    )
    assert result.overall_status == "PASS"
    assert result.promoted_stage == "demo"
    assert get_strategy_status(catalog_copy, "ST-A2") == "demo"


def get_strategy_status(catalog_path: Path, strategy: str) -> str:
    from core.strategy_registry import get_strategy_manifest

    return str(get_strategy_manifest(strategy, catalog_path).get("status", ""))
