"""Phase 5 Virtual Demo Integration Tests.

Tests the full VirtualDemoIntegrationService:
- Signal-to-order execution through VirtualBroker
- Drift checks (fill rate, PF drift)
- Evidence recording and lifecycle transition
- Report artifacts (JSON + Markdown)
- PASS/FAIL gate behaviour
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from svos.application.audit import AuditIntegrationService
from svos.application.backtest import BacktestIntegrationService
from svos.application.intake import IntakeService
from svos.application.replay import ReplayIntegrationService
from svos.application.robustness import RobustnessIntegrationService
from svos.application.virtual_demo import VirtualDemoIntegrationService
from svos.orchestration import SVOSPlatform


# ── catalog / spec ────────────────────────────────────────────────────────────

_CATALOG = """
current_strategy: null
strategies:
  LONDON-DEMO:
    status: draft
    approved: false
    current: false
    version: "1.0"
    owner: quant
    description: London session demo test strategy
    deployment_target: null
    symbols: [EURUSD]
    timeframes: [M15]
""".strip() + "\n"

_SPEC = """
Market: FX
Instrument: EURUSD
Timeframe: M15
Session: London killzone (07:00–10:00 UTC)
Direction: Long only when H1 bias is bullish
Entry Trigger: After a sweep of the prior session low, enter on CHoCH within 3 candles.
Confirmation: BOS close and three-candle FVG after displacement.
Invalidation: No CHoCH within 3 candles.
Stop Loss: 2 pips below the swept low.
Take Profit: 2R.
Risk: 0.3% fixed fractional risk per trade.
Maximum Daily Loss: 2R. Maximum Drawdown: 8%.
Maximum Open Positions: 1.
""".strip()

# 20 signals: 2/3 win, 1/3 lose
_SIGNALS = [
    {
        "entry_time": f"2024-0{(i % 9) + 1}-{(i % 28) + 1:02d}T08:00:00Z",
        "entry_price": 1.1000 + i * 0.001,
        "stop_loss": 1.0980 + i * 0.001,
        "take_profit": 1.1040 + i * 0.001,
        "side": "long",
        "result_r": 2.0 if i % 3 != 0 else -1.0,
    }
    for i in range(20)
]

_TOO_FEW_SIGNALS = _SIGNALS[:3]   # < minimum 5 → guaranteed FAIL


def _setup(tmp_path: Path) -> tuple[Path, SVOSPlatform]:
    (tmp_path / "config").mkdir(parents=True, exist_ok=True)
    catalog = tmp_path / "config" / "strategy_catalog.yaml"
    catalog.write_text(_CATALOG, encoding="utf-8")
    platform = SVOSPlatform(root=tmp_path, catalog_path=catalog)
    platform.bootstrap()
    return catalog, platform


def _advance_to_robustness(platform: SVOSPlatform) -> None:
    IntakeService(platform).run("LONDON-DEMO", _SPEC, actor="ci")
    AuditIntegrationService(platform).run("LONDON-DEMO", _SPEC, actor="ci")
    replay_trades = [
        {
            "entry_time": f"2024-0{(i % 9) + 1}-01T08:00:00Z",
            "entry_price": 1.1000,
            "stop_loss": 1.0980,
            "take_profit": 1.1040,
            "result_r": 2.0 if i % 3 != 0 else -1.0,
            "std_net_r": 2.0 if i % 3 != 0 else -1.0,
        }
        for i in range(60)
    ]
    bt_metrics = {
        "trade_count": 60,
        "profit_factor": 1.45,
        "profit_factor_2x": 1.12,
        "expectancy": 0.28,
        "max_drawdown": 6.2,
        "win_rate": 0.58,
        "spread_included": True,
        "commission_included": True,
    }
    ReplayIntegrationService(platform).run("LONDON-DEMO", replay_trades, actor="ci")
    BacktestIntegrationService(platform).run("LONDON-DEMO", bt_metrics, actor="ci")
    RobustnessIntegrationService(platform).run("LONDON-DEMO", replay_trades, actor="ci")


# ═══════════════════════════════════════════════════════════════════════════
# Basic PASS path
# ═══════════════════════════════════════════════════════════════════════════

def test_virtual_demo_pass_with_sufficient_signals(tmp_path):
    _, platform = _setup(tmp_path)
    _advance_to_robustness(platform)

    svc = VirtualDemoIntegrationService(platform)
    result = svc.run("LONDON-DEMO", _SIGNALS, actor="test")

    assert result.signal_count == 20
    assert result.version_id
    assert Path(result.report_artifact).exists()


def test_virtual_demo_report_is_valid_json(tmp_path):
    _, platform = _setup(tmp_path)
    _advance_to_robustness(platform)

    result = VirtualDemoIntegrationService(platform).run("LONDON-DEMO", _SIGNALS)

    report = json.loads(Path(result.report_artifact).read_text())
    assert report["report_type"] == "virtual_demo_report"
    assert report["stage"] == "VIRTUAL_DEMO"
    assert report["strategy"] == "LONDON-DEMO"
    assert "drift_checks" in report
    assert "summary" in report


def test_virtual_demo_report_has_markdown_companion(tmp_path):
    _, platform = _setup(tmp_path)
    _advance_to_robustness(platform)

    result = VirtualDemoIntegrationService(platform).run("LONDON-DEMO", _SIGNALS)
    md_path = Path(result.report_artifact).with_suffix(".md")

    assert md_path.exists()
    content = md_path.read_text()
    assert "Virtual Demo Report" in content
    assert "LONDON-DEMO" in content


# ═══════════════════════════════════════════════════════════════════════════
# FAIL paths
# ═══════════════════════════════════════════════════════════════════════════

def test_virtual_demo_fail_with_too_few_signals(tmp_path):
    _, platform = _setup(tmp_path)
    _advance_to_robustness(platform)

    result = VirtualDemoIntegrationService(platform).run("LONDON-DEMO", _TOO_FEW_SIGNALS)

    assert result.status == "FAIL"
    assert not result.passed
    failing = [c for c in result.drift_checks if not c["passed"]]
    assert failing


def test_virtual_demo_fail_produces_report_artifact(tmp_path):
    _, platform = _setup(tmp_path)
    _advance_to_robustness(platform)

    result = VirtualDemoIntegrationService(platform).run("LONDON-DEMO", _TOO_FEW_SIGNALS)
    assert Path(result.report_artifact).exists()
    report = json.loads(Path(result.report_artifact).read_text())
    assert report["status"] == "FAIL"


# ═══════════════════════════════════════════════════════════════════════════
# Evidence and lifecycle
# ═══════════════════════════════════════════════════════════════════════════

def test_virtual_demo_produces_evidence_record(tmp_path):
    _, platform = _setup(tmp_path)
    _advance_to_robustness(platform)

    VirtualDemoIntegrationService(platform).run("LONDON-DEMO", _SIGNALS)

    evidence = platform.registry.evidence("LONDON-DEMO")
    vd_ev = [e for e in evidence if e.get("stage") == "VIRTUAL_DEMO"]
    assert vd_ev, "No VIRTUAL_DEMO evidence recorded"
    assert vd_ev[-1]["artifact_hash"]


def test_virtual_demo_evidence_has_signal_count(tmp_path):
    _, platform = _setup(tmp_path)
    _advance_to_robustness(platform)

    VirtualDemoIntegrationService(platform).run("LONDON-DEMO", _SIGNALS)

    evidence = platform.registry.evidence("LONDON-DEMO")
    vd_ev = [e for e in evidence if e.get("stage") == "VIRTUAL_DEMO"]
    meta = vd_ev[-1].get("metadata", {})
    assert meta.get("signal_count") == 20


# ═══════════════════════════════════════════════════════════════════════════
# Result object
# ═══════════════════════════════════════════════════════════════════════════

def test_virtual_demo_result_to_dict(tmp_path):
    _, platform = _setup(tmp_path)
    _advance_to_robustness(platform)

    result = VirtualDemoIntegrationService(platform).run("LONDON-DEMO", _SIGNALS)
    d = result.to_dict()

    assert "passed" in d
    assert "signal_count" in d
    assert "filled_count" in d
    assert "drift_checks" in d
    assert "summary" in d


def test_virtual_demo_result_manifest_id_set(tmp_path):
    _, platform = _setup(tmp_path)
    _advance_to_robustness(platform)

    result = VirtualDemoIntegrationService(platform).run("LONDON-DEMO", _SIGNALS)
    assert result.manifest_id


def test_virtual_demo_summary_contains_virtual_pf(tmp_path):
    _, platform = _setup(tmp_path)
    _advance_to_robustness(platform)

    result = VirtualDemoIntegrationService(platform).run("LONDON-DEMO", _SIGNALS)
    assert "virtual_pf" in result.summary
    assert isinstance(result.summary["virtual_pf"], (int, float))


# ═══════════════════════════════════════════════════════════════════════════
# Full pipeline: all 5 research stages + virtual demo
# ═══════════════════════════════════════════════════════════════════════════

def test_full_six_stage_pipeline_produces_all_evidence(tmp_path):
    _, platform = _setup(tmp_path)
    _advance_to_robustness(platform)

    vd_result = VirtualDemoIntegrationService(platform).run("LONDON-DEMO", _SIGNALS)

    evidence = platform.registry.evidence("LONDON-DEMO")
    stages = {e["stage"] for e in evidence}
    for expected in (
        "INTAKE", "AUDIT", "HISTORICAL_REPLAY",
        "STATISTICAL_VALIDATION", "ROBUSTNESS_VALIDATION", "VIRTUAL_DEMO",
    ):
        assert expected in stages, f"Missing evidence for {expected}"

    assert Path(vd_result.report_artifact).exists()
    assert Path(vd_result.report_artifact).with_suffix(".md").exists()
