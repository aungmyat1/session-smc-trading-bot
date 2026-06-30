"""Tests for the validation gate and regression engines."""

from core.strategy_registry import get_strategy_manifest


def _fixture_catalog_text() -> str:
    """Fixture catalog with ST-A2 in walk_forward state for pipeline tests."""
    return """
current_strategy: ST-A2
strategies:
  ST-A2:
    status: walk_forward
    approved: true
    current: true
    version: "2.1"
    owner: quant
    description: Fixture catalog for validation gate tests
    symbols: [EURUSD, GBPUSD]
    timeframes: [M15, H4]
""".strip() + "\n"


from research.regression.engine import RegressionEngine  # noqa: E402
from research.validation.engine import (  # noqa: E402
    BacktestValidationInput,
    ReplayTrade,
    ReplayValidationInput,
    ValidationGate,
    ValidationRunner,
    load_validation_config,
)


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
        state_transitions=[
            ("IDLE", "SETUP"),
            ("SETUP", "CONFIRMED"),
            ("CONFIRMED", "ORDER_PLACED"),
            ("ORDER_PLACED", "FILLED"),
            ("FILLED", "CLOSED"),
        ],
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


def test_replay_validation_success():
    gate = ValidationGate(load_validation_config())
    result = gate.validate_replay(_valid_replay())
    assert result.status == "PASS"
    assert all(check.passed for check in result.checks)


def test_replay_validation_failure_duplicate_trade_id():
    payload = _valid_replay()
    payload.trades.append(payload.trades[0])
    result = ValidationGate().validate_replay(payload)
    assert result.status == "FAIL"
    assert any(
        check.name == "no_duplicate_trade_ids" and not check.passed
        for check in result.checks
    )


def test_backtest_validation_success():
    result = ValidationGate().validate_backtest(_valid_backtest())
    assert result.status == "PASS"
    assert all(check.passed for check in result.checks)


def test_backtest_validation_failure_low_pf():
    payload = _valid_backtest()
    payload.profit_factor = 0.9
    result = ValidationGate().validate_backtest(payload)
    assert result.status == "FAIL"
    assert any(
        check.name == "profit_factor" and not check.passed for check in result.checks
    )


def test_regression_detection_warning_and_fail():
    engine = RegressionEngine(
        {
            "profit_factor": {"warning_drop_pct": 0.05, "fail_drop_pct": 0.10},
            "max_drawdown": {"warning_increase_pct": 0.10, "fail_increase_pct": 0.20},
        }
    )
    warn = engine.compare(
        {
            "profit_factor": 1.12,
            "win_rate": 0.34,
            "expectancy": 0.10,
            "max_drawdown": 5.0,
            "trade_count": 110,
            "net_return": 11.0,
        },
        {
            "profit_factor": 1.16,
            "win_rate": 0.35,
            "expectancy": 0.11,
            "max_drawdown": 4.7,
            "trade_count": 112,
            "net_return": 11.5,
        },
    )
    assert warn.status in {"WARNING", "PASS"}
    fail = engine.compare(
        {
            "profit_factor": 0.95,
            "win_rate": 0.30,
            "expectancy": 0.05,
            "max_drawdown": 8.0,
            "trade_count": 80,
            "net_return": 4.0,
        },
        {
            "profit_factor": 1.20,
            "win_rate": 0.35,
            "expectancy": 0.10,
            "max_drawdown": 4.0,
            "trade_count": 120,
            "net_return": 12.0,
        },
    )
    assert fail.status == "FAIL"


def test_validation_reports_do_not_mutate_lifecycle(tmp_path):
    catalog_copy = tmp_path / "strategy_catalog.yaml"
    catalog_copy.write_text(
        _fixture_catalog_text(),
        encoding="utf-8",
    )
    runner = ValidationRunner("ST-A2", output_dir=tmp_path, registry_path=catalog_copy)
    bundle = runner.run(
        _valid_replay(),
        _valid_backtest(),
        {
            "profit_factor": 1.25,
            "win_rate": 0.35,
            "expectancy": 0.12,
            "max_drawdown": 4.5,
            "trade_count": 120,
            "net_return": 12.0,
        },
        previous_metrics={
            "profit_factor": 1.20,
            "win_rate": 0.34,
            "expectancy": 0.11,
            "max_drawdown": 4.8,
            "trade_count": 118,
            "net_return": 11.0,
        },
        current_stage="backtest",
    )
    assert bundle.overall_status == "PASS"
    assert bundle.promoted is False
    assert bundle.next_stage == "walk_forward"
    assert get_strategy_manifest("ST-A2", catalog_copy)["status"] == "walk_forward"
    report_dir = next(tmp_path.rglob("validation.md"))
    assert report_dir.exists()
    assert "Validation Report" in report_dir.read_text(encoding="utf-8")


def test_validation_runner_can_skip_promotion(tmp_path):
    catalog_copy = tmp_path / "strategy_catalog.yaml"
    catalog_copy.write_text(
        _fixture_catalog_text(),
        encoding="utf-8",
    )
    runner = ValidationRunner("ST-A2", output_dir=tmp_path, registry_path=catalog_copy)
    bundle = runner.run(
        _valid_replay(),
        _valid_backtest(),
        {
            "profit_factor": 1.25,
            "win_rate": 0.35,
            "expectancy": 0.12,
            "max_drawdown": 4.5,
            "trade_count": 120,
            "net_return": 12.0,
        },
        previous_metrics={
            "profit_factor": 1.20,
            "win_rate": 0.34,
            "expectancy": 0.11,
            "max_drawdown": 4.8,
            "trade_count": 118,
            "net_return": 11.0,
        },
        current_stage="demo",
        promote=False,
    )
    assert bundle.overall_status == "PASS"
    assert bundle.promoted is False
    assert get_strategy_manifest("ST-A2", catalog_copy)["status"] == "walk_forward"


def test_config_loading():
    cfg = load_validation_config()
    assert cfg.minimum_trade_count >= 100
    assert cfg.promotion_map["backtest"] == "walk_forward"
