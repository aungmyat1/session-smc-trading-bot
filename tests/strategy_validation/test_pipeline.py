from __future__ import annotations

import json

from strategy_validation.cli import main
from strategy_validation.pipeline.strategy_validation_pipeline import \
    StrategyValidationPipeline


def _good_spec() -> str:
    return """
# Strategy: ReplayReady

## Market / Timeframe / Session / Direction
| Instruments | EURUSD |
| Market | FX |
| Timeframe | M15 |
| Session | London 07:00-10:00 UTC |
| Direction | Long and Short |
| Position Sizing | Fixed fractional 0.5% risk per trade |
| Maximum Daily Loss | 2R |
| Maximum Drawdown | 8% |
| Maximum Open Positions | 1 |
| News Rules | Do not open trades within 15 minutes of high-impact EUR or USD news |

## Entry Rules
1. Enter long when price sweeps the prior day's low by at least 2 pips and closes back above that low.
2. Confirm BOS on M15 with close > prior swing high.
3. Require ATR(14) >= 0.0008 and displacement candle body > 1.2 x ATR(14).

## Exit Rules
1. Stop Loss: 3 pips below the sweep low.
2. Take Profit: 2R fixed target.
3. Cancel if BOS does not occur within 3 candles after the sweep.

## Risk Model
Use fixed fractional risk of 0.5% with a hard daily stop at 2R and weekly stop at 5R.

## Trading Philosophy
The setup exists because liquidity sweeps followed by BOS mark a measurable reversal.

## Confirmation Rules
Use liquidity sweep, BOS, market structure, and session filter only.
""".strip()


def _bad_spec() -> str:
    return """
# Strategy: FuzzyEdge

Trade only London.
Trade only Asian.
Look for a strong trend and good momentum near support.
Use a large candle for confirmation.
Maximum 2 trades/day.
Unlimited entries allowed.
Stop Loss: below sweep.
Take Profit: let winners run.
""".strip()


def test_pipeline_ready_spec_passes():
    pipeline = StrategyValidationPipeline()
    report = pipeline.run_text(_good_spec())

    assert report.strategy_name == "ReplayReady"
    assert report.overall_score >= 80
    assert report.readiness_decision in {"READY_FOR_REPLAY", "REQUIRES_REVISION"}
    assert any(
        result.validator_name == "Input Validation"
        for result in report.validator_results
    )


def test_pipeline_detects_stage1_issues():
    pipeline = StrategyValidationPipeline()
    report = pipeline.run_text(_bad_spec())

    assert report.overall_status == "FAIL"
    assert report.readiness_decision in {"REJECTED", "INCOMPLETE"}
    assert any(
        "Subjective wording" in finding.message
        for result in report.validator_results
        for finding in result.findings
    )
    assert any(
        "daily trade cap" in finding.message
        for result in report.validator_results
        for finding in result.findings
    )


def test_report_files_are_written(tmp_path):
    pipeline = StrategyValidationPipeline()
    report = pipeline.run_text(_good_spec())

    written = pipeline.write_report(report, tmp_path / report.strategy_name)
    payload = json.loads(written["json"].read_text(encoding="utf-8"))

    assert written["markdown"].exists()
    assert written["html"].exists()
    assert written["audit_log"].exists()
    assert payload["strategy_name"] == "ReplayReady"


def test_cli_generates_reports(tmp_path, capsys):
    spec_path = tmp_path / "spec.md"
    spec_path.write_text(_good_spec(), encoding="utf-8")

    exit_code = main(["--spec", str(spec_path), "--outdir", str(tmp_path / "reports")])
    captured = capsys.readouterr()

    assert "ReplayReady" in captured.out
    assert exit_code in {0, 1}
    assert (tmp_path / "reports" / "ReplayReady" / "validation_report.json").exists()
