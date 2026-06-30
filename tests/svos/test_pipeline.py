"""Full-pipeline integration tests — StrategyPipeline chains all 6 phases.

Tests:
- Full PASS through all phases produces approval package
- FAIL at Intake stops early, later phases SKIPPED
- FAIL at Replay stops early
- Evidence accumulated for all completed phases
- Approval package JSON is valid and complete
- PipelineResult.to_dict() is serializable
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from svos.application.pipeline import StrategyPipeline, PipelineResult
from svos.orchestration import SVOSPlatform


_CATALOG = """
current_strategy: null
strategies:
  PIPELINE-TEST:
    status: draft
    approved: false
    current: false
    version: "1.0"
    owner: quant
    description: Pipeline integration test strategy
    deployment_target: null
    symbols: [EURUSD]
    timeframes: [M15]
""".strip() + "\n"

_SPEC = """Strategy: London BOS Reversal
Instrument: EURUSD
Market: FX
Timeframe: M15
Session: London killzone 07:00-10:00 UTC
Direction: Long only when H1 bias is bullish; short only when bearish
Entry Rules: When session filter confirms London killzone, enter long after liquidity sweep of prior session low at a discount zone below a key level. Wait for BOS then CHoCH with market structure confirmation. Cancel if no CHoCH within 3 candles.
Exit Rules: Take profit at 2R from entry at premium level. Stop loss 2 pips below swept low. Break-even at 1R. Reject and skip if spread exceeds 2 pips.
Stop Loss: 2 pips below the swept low
Take Profit: 2R
Risk Model: 0.3% fixed fractional risk per trade. Kill switch at 2R daily loss.
Position Sizing: 0.3% of account equity per trade, 0.01 lots per 1000 USD.
Maximum Daily Loss: 2R
Maximum Drawdown: 8%
Maximum Open Positions: 1
News Rules: No trading within 30 minutes before or after high-impact news events (FOMC, NFP, CPI).
Invalidation: No CHoCH within 3 candles; high-impact news within session window; timeout after 3 bars.
""".strip()

_BAD_SPEC = "Buy when price goes up. Sell when it goes down."

_TRADES = [
    {
        "entry_time": f"2024-0{(i % 9) + 1}-{(i % 28) + 1:02d}T08:00:00Z",
        "entry_price": 1.1000 + i * 0.001,
        "stop_loss": 1.0980 + i * 0.001,
        "take_profit": 1.1040 + i * 0.001,
        "side": "long",
        "result_r": 2.0 if i % 3 != 0 else -1.0,
        "std_net_r": 2.0 if i % 3 != 0 else -1.0,
    }
    for i in range(60)
]

_METRICS = {
    "trade_count": 60,
    "profit_factor": 1.45,
    "profit_factor_2x": 1.12,
    "expectancy": 0.28,
    "max_drawdown": 6.2,
    "win_rate": 0.58,
    "spread_included": True,
    "commission_included": True,
}

_SIGNALS = [
    {
        "entry_time": f"2024-0{(i % 9) + 1}-{(i % 28) + 1:02d}T09:00:00Z",
        "entry_price": 1.1000 + i * 0.001,
        "stop_loss": 1.0980 + i * 0.001,
        "take_profit": 1.1040 + i * 0.001,
        "side": "long",
        "result_r": 2.0 if i % 3 != 0 else -1.0,
    }
    for i in range(20)
]


def _setup(tmp_path: Path) -> SVOSPlatform:
    (tmp_path / "config").mkdir(parents=True, exist_ok=True)
    catalog = tmp_path / "config" / "strategy_catalog.yaml"
    catalog.write_text(_CATALOG, encoding="utf-8")
    platform = SVOSPlatform(root=tmp_path, catalog_path=catalog)
    platform.bootstrap()
    return platform


# ═══════════════════════════════════════════════════════════════════════════
# Full PASS pipeline
# ═══════════════════════════════════════════════════════════════════════════

def test_pipeline_full_pass_all_six_phases(tmp_path):
    platform = _setup(tmp_path)
    result = StrategyPipeline(platform).run(
        "PIPELINE-TEST", _SPEC,
        trades=_TRADES, metrics=_METRICS, signals=_SIGNALS,
        actor="ci",
    )

    assert result.passed
    assert result.status == "PASS"
    assert result.failed_phase is None
    assert len(result.completed_phases) == 6
    assert len(result.phases) == 6


def test_pipeline_full_pass_writes_approval_package(tmp_path):
    platform = _setup(tmp_path)
    result = StrategyPipeline(platform).run(
        "PIPELINE-TEST", _SPEC,
        trades=_TRADES, metrics=_METRICS, signals=_SIGNALS,
    )

    assert result.approval_package_path
    pkg_path = Path(result.approval_package_path)
    assert pkg_path.exists()
    pkg = json.loads(pkg_path.read_text())
    assert pkg["status"] == "APPROVED_PHASE5"
    assert pkg["strategy"] == "PIPELINE-TEST"
    assert "manifest_hash" in pkg


def test_pipeline_approval_package_has_all_evidence_ids(tmp_path):
    platform = _setup(tmp_path)
    result = StrategyPipeline(platform).run(
        "PIPELINE-TEST", _SPEC,
        trades=_TRADES, metrics=_METRICS, signals=_SIGNALS,
    )

    pkg = json.loads(Path(result.approval_package_path).read_text())
    for phase in ("INTAKE", "AUDIT", "REPLAY", "BACKTEST", "ROBUSTNESS", "VIRTUAL_DEMO"):
        assert phase in pkg["evidence_ids"], f"Missing evidence_id for {phase}"


def test_pipeline_all_phases_have_report_artifacts(tmp_path):
    platform = _setup(tmp_path)
    result = StrategyPipeline(platform).run(
        "PIPELINE-TEST", _SPEC,
        trades=_TRADES, metrics=_METRICS, signals=_SIGNALS,
    )

    for outcome in result.phases:
        assert outcome.status == "PASS"
        assert Path(outcome.report_artifact).exists(), f"{outcome.phase} artifact missing"


def test_pipeline_evidence_summary_covers_all_phases(tmp_path):
    platform = _setup(tmp_path)
    result = StrategyPipeline(platform).run(
        "PIPELINE-TEST", _SPEC,
        trades=_TRADES, metrics=_METRICS, signals=_SIGNALS,
    )

    for phase in ("INTAKE", "AUDIT", "REPLAY", "BACKTEST", "ROBUSTNESS", "VIRTUAL_DEMO"):
        assert phase in result.evidence_summary
        assert result.evidence_summary[phase]


def test_pipeline_result_to_dict_is_json_serializable(tmp_path):
    platform = _setup(tmp_path)
    result = StrategyPipeline(platform).run(
        "PIPELINE-TEST", _SPEC,
        trades=_TRADES, metrics=_METRICS, signals=_SIGNALS,
    )
    d = result.to_dict()
    serialized = json.dumps(d)  # must not raise
    assert json.loads(serialized)["status"] == "PASS"


def test_pipeline_phase_elapsed_times_are_positive(tmp_path):
    platform = _setup(tmp_path)
    result = StrategyPipeline(platform).run(
        "PIPELINE-TEST", _SPEC,
        trades=_TRADES, metrics=_METRICS, signals=_SIGNALS,
    )

    for outcome in result.phases:
        assert outcome.elapsed_s >= 0


# ═══════════════════════════════════════════════════════════════════════════
# FAIL at Intake — bad spec
# ═══════════════════════════════════════════════════════════════════════════

def test_pipeline_fail_at_intake_stops_early(tmp_path):
    platform = _setup(tmp_path)
    result = StrategyPipeline(platform).run(
        "PIPELINE-TEST", _BAD_SPEC,
        trades=_TRADES, metrics=_METRICS, signals=_SIGNALS,
    )

    # Intake should FAIL (bad spec), rest skipped
    assert not result.passed
    assert result.status == "FAIL"
    assert result.failed_phase is not None
    assert result.approval_package_path == ""

    skipped = [p for p in result.phases if p.status == "SKIPPED"]
    assert skipped  # at least some phases are skipped


def test_pipeline_fail_skipped_phases_have_no_artifacts(tmp_path):
    platform = _setup(tmp_path)
    result = StrategyPipeline(platform).run(
        "PIPELINE-TEST", _BAD_SPEC,
        trades=_TRADES, metrics=_METRICS, signals=_SIGNALS,
    )

    skipped = [p for p in result.phases if p.status == "SKIPPED"]
    for p in skipped:
        assert p.report_artifact == ""
        assert p.evidence_id == ""
        assert p.elapsed_s == 0.0


# ═══════════════════════════════════════════════════════════════════════════
# FAIL at Backtest — bad metrics
# ═══════════════════════════════════════════════════════════════════════════

def test_pipeline_fail_at_backtest_skips_robustness_and_demo(tmp_path):
    platform = _setup(tmp_path)
    bad_metrics = {
        "trade_count": 10,
        "profit_factor": 0.7,
        "profit_factor_2x": 0.5,
        "expectancy": -0.3,
        "max_drawdown": 20.0,
        "win_rate": 0.3,
        "spread_included": True,
        "commission_included": True,
    }
    result = StrategyPipeline(platform).run(
        "PIPELINE-TEST", _SPEC,
        trades=_TRADES, metrics=bad_metrics, signals=_SIGNALS,
    )

    phase_map = {p.phase: p for p in result.phases}
    assert phase_map["INTAKE"].status == "PASS"
    assert phase_map["AUDIT"].status == "PASS"
    assert phase_map["REPLAY"].status == "PASS"
    assert phase_map["BACKTEST"].status == "FAIL"
    assert phase_map["ROBUSTNESS"].status == "SKIPPED"
    assert phase_map["VIRTUAL_DEMO"].status == "SKIPPED"
    assert result.failed_phase == "BACKTEST"


# ═══════════════════════════════════════════════════════════════════════════
# Evidence accumulation
# ═══════════════════════════════════════════════════════════════════════════

def test_pipeline_platform_evidence_covers_all_passed_stages(tmp_path):
    platform = _setup(tmp_path)
    StrategyPipeline(platform).run(
        "PIPELINE-TEST", _SPEC,
        trades=_TRADES, metrics=_METRICS, signals=_SIGNALS,
    )

    evidence = platform.registry.evidence("PIPELINE-TEST")
    stages = {e["stage"] for e in evidence}
    for expected in ("INTAKE", "AUDIT", "HISTORICAL_REPLAY", "STATISTICAL_VALIDATION",
                     "ROBUSTNESS_VALIDATION", "VIRTUAL_DEMO"):
        assert expected in stages


def test_pipeline_partial_run_evidence_stops_at_failed_phase(tmp_path):
    platform = _setup(tmp_path)
    StrategyPipeline(platform).run(
        "PIPELINE-TEST", _BAD_SPEC,
        trades=_TRADES, metrics=_METRICS, signals=_SIGNALS,
    )

    evidence = platform.registry.evidence("PIPELINE-TEST")
    stages = {e["stage"] for e in evidence}
    # VIRTUAL_DEMO was skipped, so no evidence for it
    assert "VIRTUAL_DEMO" not in stages
    assert "STATISTICAL_VALIDATION" not in stages
