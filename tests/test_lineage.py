from __future__ import annotations

from execution_validation.engine import ExecutionValidationReport
from research.lineage import build_lineage_metadata, build_release_metadata


def test_build_release_metadata_has_code_and_tag():
    meta = build_release_metadata()
    assert "code_version" in meta
    assert "release_tag" in meta
    assert "release_dirty" in meta


def test_lineage_metadata_embeds_release_fields():
    meta = build_lineage_metadata(
        source="test",
        strategy="ST-A2",
        strategy_version="2.1.3",
        artifact="demo",
    )
    assert meta["source"] == "test"
    assert meta["strategy"] == "ST-A2"
    assert "release_tag" in meta
    assert "code_version" in meta


def test_execution_validation_report_includes_release():
    report = ExecutionValidationReport(strategy="ST-A2", period="2026-06")
    payload = report.to_dict()
    assert "release" in payload
    assert "code_version" in payload["release"]
