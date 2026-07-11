from __future__ import annotations

from research.failure_decomposition import session_attribution


def test_session_attribution_normalizes_new_york_name(sample_decomposition_rows) -> None:
    report = session_attribution(sample_decomposition_rows)

    assert "NewYork" in report["sessions"]
    assert "London" in report["sessions"]
    assert report["best_session"] == "NewYork"
