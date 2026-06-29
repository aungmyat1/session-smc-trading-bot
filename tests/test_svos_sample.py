from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.run_svos_sample import REPORTS, run_sample


ROOT = Path(__file__).resolve().parents[1]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_isolated_sample_runs_and_verifies_all_six_reports(tmp_path):
    catalog = ROOT / "config" / "strategy_catalog.yaml"
    catalog_before = _sha256(catalog)

    result = run_sample(tmp_path / "reports" / "svos")

    assert result["overall_status"] == "PASS"
    assert result["reports_verified"] == 6
    assert result["strategy_id"] == "SVOS-SAMPLE"
    assert result["strategy_version"] == "1.0.0"
    assert result["isolated_catalog_final_status"] == "demo"
    assert result["live_promotion_requested"] is False
    assert [stage["stage"] for stage in result["stages"]] == [stage for stage, _ in REPORTS]
    assert [stage["status"] for stage in result["stages"]] == ["PASS"] * 6
    assert result["stages"][-1]["promotion_allowed"] is False
    assert _sha256(catalog) == catalog_before

    report_dir = Path(result["report_dir"])
    summary = json.loads((report_dir / "run_summary.json").read_text(encoding="utf-8"))
    assert summary["latest_passed_stage"] == "production_approval"
    assert summary["active_blocker"] == ""
    # Six stage reports, the run summary, and five cross-stage evidence reports.
    assert len(list(report_dir.glob("*.json"))) == 12
    assert len(list(report_dir.glob("*.md"))) == 12


def test_sample_virtual_demo_report_contains_execution_evidence(tmp_path):
    result = run_sample(tmp_path / "reports" / "svos")
    report_dir = Path(result["report_dir"])
    report = json.loads((report_dir / "05_virtual_demo.json").read_text(encoding="utf-8"))

    execution = report["metrics"]["execution"]
    assert execution["expected_signals"] == execution["observed_signals"] == 12
    assert execution["expected_trades"] == execution["observed_trades"] == 5
    assert execution["order_outcomes"]["rejected"] == 0
    assert execution["risk_controls"]["position_sizing"] is True
    assert execution["execution_metrics"]["latency_ms"] == 90
