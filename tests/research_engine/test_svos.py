from pathlib import Path

from research.svos.engine import (
    DemoValidationInput,
    RobustnessValidationInput,
    SVOSRunner,
    StrategyAuditEngine,
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
        ),
        promote=True,
        allow_live_promotion=True,
    )
    assert result.overall_status == "PASS"
    assert result.stages[-1].stage == "production_approval"
    assert result.stages[-1].status == "PASS"
    assert result.promoted_stage == "live"
    assert Path(tmp_path / "ST-A2" / "svos_result.json").exists()
    assert get_strategy_status(catalog_copy, "ST-A2") == "live"


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
        ),
    )
    assert result.overall_status == "FAIL"
    assert any(stage.stage == "demo" and stage.status == "FAIL" for stage in result.stages)
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
