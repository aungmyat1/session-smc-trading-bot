from __future__ import annotations

from research.failure_decomposition import failure_breakdown


def test_failure_breakdown_reports_target_gaps(sample_decomposition_rows) -> None:
    report = failure_breakdown(sample_decomposition_rows)

    assert report["performance"]["trade_count"] == 4
    assert "trade_count" in report["gap_analysis"]["primary_failures"]
    assert report["stability"]["monthly_profit_factor"]
