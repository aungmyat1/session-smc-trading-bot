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


def _fixture_catalog_text() -> str:
    """Fixture catalog with ST-A2 in an approved/walk_forward state.

    Tests that exercise the SVOS pipeline need a strategy in the catalog that can
    be approved for demo — they should not depend on the real catalog's current state.
    """
    return """
current_strategy: ST-A2
strategies:
  ST-A2:
    status: walk_forward
    approved: true
    current: true
    version: "2.1"
    owner: quant
    description: Fixture catalog for SVOS pipeline tests
    deployment_target: execution
    symbols: [EURUSD, GBPUSD]
    timeframes: [M15, H4]
""".strip() + "\n"


def _complete_strategy_text() -> str:
    return """
Market: FX
Instruments: EURUSD
Timeframe: M15
Session: London and New York killzones only
Direction: Long only when H1 bias is bullish
Bias: Bullish market structure with BOS close beyond prior swing high by at least 1 pip
Entry Trigger: During London or New York, wait for a liquidity sweep of the prior session low by at least 2 pips, then enter on the first M15 close that confirms CHOCH within 3 candles
Confirmation: Require BOS close beyond the prior swing and a three-candle FVG of at least 1 pip because the setup is only valid after measurable displacement
Invalidation: Cancel the setup if CHOCH does not occur within 3 candles after the sweep or if price closes back below the swept low before entry
Entry Rules: Enter on the first qualifying M15 confirmation candle close during the active killzone after the sweep and CHOCH sequence completes
Stop Loss: Place stop loss 2 pips below the swept low
Take Profit: 2R
Risk: 0.3% fixed fractional risk per trade
Risk Model: Fixed fractional risk of 0.3% per trade, maximum daily loss 2R, maximum drawdown 8%
Position Sizing: Size the position from stop distance so account risk equals 0.3%
Maximum Daily Loss: 2R
Maximum Drawdown: 8%
Maximum Open Positions: 1
News Rules: No new trades within 15 minutes of high-impact EUR or USD news
Filters: HTF bias, session filter, spread must remain below 1.5 pips
Exit Rules: Close the full position at 2R, stop out at the defined stop loss, and cancel the setup if confirmation expires before entry
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
    catalog_copy.write_text(_fixture_catalog_text(), encoding="utf-8")
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


def test_runner_audit_stage_uses_canonical_strategy_validation_report(tmp_path):
    catalog_copy = tmp_path / "strategy_catalog.yaml"
    catalog_copy.write_text(_fixture_catalog_text(), encoding="utf-8")
    runner = SVOSRunner("ST-A2", registry_path=catalog_copy, output_dir=tmp_path)
    result = runner.run_pipeline(_complete_strategy_text(), stop_after="audit")

    assert result.stages[-1].stage == "audit"
    assert result.stages[-1].status == "PASS"
    assert "validation_report" in result.stages[-1].metadata
    assert result.stages[-1].metadata["validation_report"]["readiness_decision"] == "READY_FOR_REPLAY"
    assert (tmp_path / "ST-A2" / "stages" / "01_audit.json").exists()


def test_runner_enhancement_stage_produces_structured_editor_plan(tmp_path):
    catalog_copy = tmp_path / "strategy_catalog.yaml"
    catalog_copy.write_text(_fixture_catalog_text(), encoding="utf-8")
    runner = SVOSRunner("ST-A2", registry_path=catalog_copy, output_dir=tmp_path)
    result = runner.run_pipeline(_complete_strategy_text(), stop_after="enhancement")

    enhancement = result.stages[-1]
    assert enhancement.stage == "enhancement"
    assert enhancement.status == "PASS"
    assert "enhancement_plan" in enhancement.metadata
    plan = enhancement.metadata["enhancement_plan"]
    assert plan["status"] in {"READY", "READY_WITH_SUGGESTIONS"}
    assert "questions" in plan
    assert isinstance(plan["questions"], list)
    assert (tmp_path / "ST-A2" / "stages" / "02_enhancement.md").exists()


def test_runner_generates_enhancement_stage_for_failed_audit(tmp_path):
    catalog_copy = tmp_path / "strategy_catalog.yaml"
    catalog_copy.write_text(_fixture_catalog_text(), encoding="utf-8")
    runner = SVOSRunner("ST-A2", registry_path=catalog_copy, output_dir=tmp_path)
    result = runner.run_pipeline("London Session\nLiquidity Sweep\nRR 1:2\nRisk 0.3%")

    assert result.overall_status == "FAIL"
    assert [stage.stage for stage in result.stages] == ["intake", "audit", "enhancement"]
    audit_stage = result.stages[1]
    enhancement_stage = result.stages[2]
    assert audit_stage.status in {"FIX", "FAIL"}
    assert enhancement_stage.stage == "enhancement"
    assert enhancement_stage.status == "FIX"
    assert enhancement_stage.metadata["enhancement_plan"]["status"] == "ACTION_REQUIRED"
    assert enhancement_stage.clarifying_questions
    assert (tmp_path / "ST-A2" / "stages" / "02_enhancement.json").exists()


def test_runner_can_stop_at_verification_ready(tmp_path):
    catalog_copy = tmp_path / "strategy_catalog.yaml"
    catalog_copy.write_text(_fixture_catalog_text(), encoding="utf-8")
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
    catalog_copy.write_text(_fixture_catalog_text(), encoding="utf-8")
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
    catalog_copy.write_text(_fixture_catalog_text(), encoding="utf-8")
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
    approval_report = json.loads(
        (Path(result.canonical_report["report_dir"]) / "06_production_approval.json").read_text(encoding="utf-8")
    )
    assert approval_report["status"] == "PASS"
    assert approval_report["promotion_allowed"] is False


def test_runner_writes_immutable_six_stage_report_package(tmp_path):
    catalog_copy = tmp_path / "strategy_catalog.yaml"
    catalog_copy.write_text(_fixture_catalog_text(), encoding="utf-8")
    runner = SVOSRunner("ST-A2", registry_path=catalog_copy, output_dir=tmp_path / "legacy")
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
            latest_metrics={"profit_factor": 1.22, "win_rate": 0.36, "expectancy": 0.11, "max_drawdown": 4.8},
            previous_metrics={"profit_factor": 1.20, "win_rate": 0.35, "expectancy": 0.10, "max_drawdown": 4.7},
        ),
        virtual_demo=DemoValidationInput(
            completed_successfully=True,
            days_monitored=20,
            min_demo_days=14,
            tolerance_pct=0.10,
            research_metrics={"profit_factor": 1.20, "win_rate": 0.35, "expectancy": 0.10, "max_drawdown": 4.7},
            live_metrics={"profit_factor": 1.18, "win_rate": 0.34, "expectancy": 0.099, "max_drawdown": 4.9},
            execution_validation_report=_valid_execution_report(),
            expected_signals=12,
            observed_signals=12,
            expected_trades=5,
            observed_trades=5,
            execution_metrics={"average_spread_pips": 0.8, "slippage_pips": 0.1, "latency_ms": 90},
            order_outcomes={"rejected": 0, "missed": 0, "duplicated": 0, "delayed": 0},
            risk_controls={"position_sizing": True, "daily_loss_limit": True},
        ),
        promote=True,
        allow_live_promotion=True,
    )

    report_dir = Path(result.canonical_report["report_dir"])
    expected_stems = [
        "01_strategy_audit",
        "02_historical_replay",
        "03_backtest",
        "04_robustness",
        "05_virtual_demo",
        "06_production_approval",
    ]
    assert report_dir.parent.parent.parent == tmp_path / "reports" / "svos"
    assert (report_dir / "run_summary.json").exists()
    assert (report_dir / "run_summary.md").exists()
    for stem in expected_stems:
        assert (report_dir / f"{stem}.json").exists()
        assert (report_dir / f"{stem}.md").exists()

    summary = json.loads((report_dir / "run_summary.json").read_text(encoding="utf-8"))
    assert summary["overall_status"] == "PASS"
    assert [stage["status"] for stage in summary["stages"]] == ["PASS"] * 6
    demo_report = json.loads((report_dir / "05_virtual_demo.json").read_text(encoding="utf-8"))
    assert demo_report["metrics"]["execution"]["expected_signals"] == 12
    assert demo_report["promotion_allowed"] is True
    assert demo_report["evidence_hashes"]["strategy_spec"]
    assert (tmp_path / "data" / "svos" / "reports" / "index.json").exists()
    assert (tmp_path / "data" / "svos" / "registry" / "ST-A2" / "evidence.jsonl").exists()


def test_canonical_reports_block_downstream_stages_after_missing_replay(tmp_path):
    catalog_copy = tmp_path / "strategy_catalog.yaml"
    catalog_copy.write_text(_fixture_catalog_text(), encoding="utf-8")
    result = SVOSRunner("ST-A2", registry_path=catalog_copy, output_dir=tmp_path / "legacy").run_pipeline(
        _complete_strategy_text()
    )

    report_dir = Path(result.canonical_report["report_dir"])
    summary = json.loads((report_dir / "run_summary.json").read_text(encoding="utf-8"))
    statuses = {stage["stage"]: stage["status"] for stage in summary["stages"]}
    assert statuses["strategy_audit"] == "PASS"
    assert statuses["historical_replay"] == "BLOCKED"
    assert statuses["backtest"] == "BLOCKED"
    assert statuses["production_approval"] == "BLOCKED"
    assert summary["active_blocker"] == "historical_replay"


def test_virtual_demo_drift_routes_back_to_backtest(tmp_path):
    catalog_copy = tmp_path / "strategy_catalog.yaml"
    catalog_copy.write_text(_fixture_catalog_text(), encoding="utf-8")
    result = SVOSRunner("ST-A2", registry_path=catalog_copy, output_dir=tmp_path / "legacy").run_pipeline(
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
            latest_metrics={"profit_factor": 1.22, "win_rate": 0.36, "expectancy": 0.11, "max_drawdown": 4.8},
            previous_metrics={"profit_factor": 1.20, "win_rate": 0.35, "expectancy": 0.10, "max_drawdown": 4.7},
        ),
        virtual_demo=DemoValidationInput(
            completed_successfully=True,
            days_monitored=20,
            min_demo_days=14,
            tolerance_pct=0.05,
            research_metrics={"profit_factor": 1.20, "win_rate": 0.35, "expectancy": 0.10, "max_drawdown": 4.7},
            live_metrics={"profit_factor": 0.80, "win_rate": 0.25, "expectancy": 0.02, "max_drawdown": 8.0},
            execution_validation_report=_valid_execution_report(),
        ),
    )

    report_dir = Path(result.canonical_report["report_dir"])
    demo = json.loads((report_dir / "05_virtual_demo.json").read_text(encoding="utf-8"))
    approval = json.loads((report_dir / "06_production_approval.json").read_text(encoding="utf-8"))
    assert demo["status"] == "FAIL"
    assert demo["remediation"]["route"] == "backtest"
    assert demo["promotion_allowed"] is False
    assert approval["status"] == "BLOCKED"
    assert get_strategy_status(catalog_copy, "ST-A2") != "live"


def test_changed_spec_creates_patch_version_without_overwriting_reports(tmp_path):
    catalog_copy = tmp_path / "strategy_catalog.yaml"
    catalog_copy.write_text(_fixture_catalog_text(), encoding="utf-8")
    first = SVOSRunner("ST-A2", registry_path=catalog_copy, output_dir=tmp_path / "legacy").run_pipeline(
        _complete_strategy_text(), stop_after="audit"
    )
    revised = _complete_strategy_text().replace("Take Profit: 2R", "Take Profit: 3R")
    second = SVOSRunner("ST-A2", registry_path=catalog_copy, output_dir=tmp_path / "legacy").run_pipeline(
        revised, stop_after="audit"
    )

    first_dir = Path(first.canonical_report["report_dir"])
    second_dir = Path(second.canonical_report["report_dir"])
    assert first.canonical_report["strategy_id"] == second.canonical_report["strategy_id"] == "ST-A2"
    assert first.canonical_report["strategy_version"] == "2.1"
    assert second.canonical_report["strategy_version"] == "2.1.1"
    assert first_dir.exists()
    assert second_dir.exists()
    assert first_dir != second_dir


def get_strategy_status(catalog_path: Path, strategy: str) -> str:
    from core.strategy_registry import get_strategy_manifest

    return str(get_strategy_manifest(strategy, catalog_path).get("status", ""))
